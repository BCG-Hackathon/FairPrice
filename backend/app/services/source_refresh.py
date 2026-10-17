"""Fixed-source ingestion + tiny anomaly auditor. No arbitrary URLs or LLM prices."""
import csv
import hashlib
import importlib.util
import io
import json
import logging
import math
import statistics
import threading
import urllib.request
from datetime import date, datetime, timezone
from functools import lru_cache
from urllib.parse import urlsplit, parse_qs
from urllib.error import HTTPError, URLError
from sqlalchemy import select
from app.models import PublishedPrice, SourceRefreshRun
from app.services.published import ROOT, ARTIFACTS

METADATA_URL = "https://data.humdata.org/api/3/action/package_show?id=wfp-food-prices-for-uganda"
RESOURCE_URL = "https://data.humdata.org/dataset/883929b1-521e-4834-97f5-0ccc2df75b89/resource/e082d683-cad5-4dcd-bf54-db76ae254d33/download/wfp_food_prices_uga.csv"
MAX_BYTES = 12 * 1024 * 1024
LOCK = threading.Lock()


def validate_url(url):
    parts = urlsplit(url)
    if parts.scheme != "https" or parts.port not in (None, 443) or parts.username or parts.password:
        raise ValueError("Source URL is not on the HTTPS allowlist")
    # HDX's observed official redirect, restricted to this Uganda resource only.
    if parts.hostname == "s3.us-east-1.amazonaws.com" and parts.path == "/hdx-production-filestore/resources/e082d683-cad5-4dcd-bf54-db76ae254d33/wfp_food_prices_uga.csv":
        if set(parse_qs(parts.query)) <= {"AWSAccessKeyId","Signature","x-amz-security-token","Expires"}:
            return
    if parts.hostname != "data.humdata.org":
        raise ValueError("Source URL is not on the HTTPS allowlist")
    if url not in {METADATA_URL, RESOURCE_URL}:
        raise ValueError("Unexpected Uganda source resource")


class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch_bytes(url, limit=MAX_BYTES):
    validate_url(url)
    opener = urllib.request.build_opener(SafeRedirect())
    request = urllib.request.Request(url, headers={"User-Agent": "FairPrice-source-refresh/0.1", "Accept": "application/json,text/csv"})
    with opener.open(request, timeout=25) as response:
        validate_url(response.url)
        if int(response.headers.get("Content-Length", 0)) > limit:
            raise ValueError("Source response exceeds byte limit")
        data = response.read(limit + 1)
        if len(data) > limit:
            raise ValueError("Source response exceeds byte limit")
        return data


@lru_cache(maxsize=1)
def ml_config():
    spec = importlib.util.spec_from_file_location("fairprice_ingestion_config", ROOT / "ml" / "config.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@lru_cache(maxsize=1)
def auditor():
    """32-tree IsolationForest on historical adjacent-month log changes, ~small local model."""
    from sklearn.ensemble import IsolationForest
    series = {}
    cfg = ml_config()
    with cfg.PROCESSED_FILE.open(encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            key = (row["crop"], row["market"], row["pricetype"])
            series.setdefault(key, []).append((row["month"][:7], float(row["price"])))
    changes = []
    for rows in series.values():
        rows.sort()
        for (a,p),(b,q) in zip(rows, rows[1:]):
            ay,am=map(int,a.split("-"));by,bm=map(int,b.split("-"))
            if (by-ay)*12+bm-am == 1 and p>0 and q>0:
                changes.append([math.log(q/p)])
    model = IsolationForest(n_estimators=32, max_samples=256, contamination=0.01, random_state=42, n_jobs=1)
    model.fit(changes)
    return model, len(changes)


def parse_csv(content, today=None):
    """Strict schema/unit/region checks; monthly medians; no future-looking cleaning."""
    cfg = ml_config()
    reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig")))
    required = {"date","admin1","market","commodity","unit","currency","pricetype","price","priceflag","latitude","longitude"}
    if not required.issubset(reader.fieldnames or []):
        raise ValueError("Source CSV schema changed")
    now = today or date.today()
    grouped = {}
    rejected = 0
    for index,row in enumerate(reader):
        if index > 100000:
            raise ValueError("Source row limit exceeded")
        if row["date"].startswith("#"):
            continue
        if row["admin1"] not in cfg.SUB_REGION_BY_DISTRICT or row["commodity"] not in cfg.CROP_BY_COMMODITY:
            continue
        if row["currency"] != "UGX" or row["unit"].upper() != "KG" or row["pricetype"] not in cfg.PRICE_TYPES or row["priceflag"] not in {"actual","aggregate"}:
            rejected += 1; continue
        day = date.fromisoformat(row["date"])
        value = float(row["price"])
        lat,lon = float(row["latitude"]),float(row["longitude"])
        if day > now or not math.isfinite(value) or value <= 0 or value > 1000000 or not (-90<=lat<=90 and -180<=lon<=180):
            raise ValueError("Invalid, future-dated or implausible source observation")
        crop = cfg.CROP_BY_COMMODITY[row["commodity"]]
        key = (crop,row["market"],row["pricetype"],day.strftime("%Y-%m"))
        grouped.setdefault(key, {"values": [],"district":row["admin1"],"lat":lat,"lon":lon})["values"].append(value)
    if len(grouped) < 12 or {k[0] for k in grouped} != set(cfg.CROPS):
        raise ValueError("Incomplete crop coverage; previous database preserved")
    factors=json.loads((ARTIFACTS/"market_price_factors.json").read_text())["factors"]
    latest={}
    for (crop,market,kind,month),g in grouped.items():
        key=(crop,market);rank=(month,kind=="Wholesale")
        if key in latest and rank <= latest[key][0]:continue
        observed=statistics.median(g["values"])
        factor=1.0 if kind=="Wholesale" else factors[crop]["factor"]
        region=cfg.SUB_REGION_BY_DISTRICT[g["district"]]
        latest[key]=(rank,{"crop":crop,"crop_name":cfg.CROP_NAMES[crop],"market":market,"district":g["district"],
            "sub_region":region,"core_area":region in cfg.CORE_SUB_REGIONS,"observed_price_type":kind,
            "unit":"UGX/kg","observed_price":round(observed),"last_month":month,
            "forecast_month":None,"observed_forecast":None,"change_pct":None,"forecast_method":"not_refreshed",
            "history_months":sum(1 for c,m,t,d in grouped if (c,m,t)==(crop,market,kind)),
            "latitude":g["lat"],"longitude":g["lon"],"source":cfg.SOURCE,
            "market_factor":factor,"market_factor_basis":"observed wholesale" if kind=="Wholesale" else factors[crop]["basis"],
            "market_price":math.floor(observed*factor+0.5),"market_price_forecast":None})
    rows=[r for _,r in latest.values()]
    return rows,{"monthly_observations":len(grouped),"excluded_unit_or_flag_rows":rejected,"latest_month":max(r["last_month"] for r in rows)}


def refresh_source(db, settings, fetcher=fetch_bytes):
    """Fail closed on schema/anomaly/coverage errors. Successful publication is transactional."""
    if not LOCK.acquire(blocking=False):
        return {"status":"already_running"}
    details={"source":"WFP/HDX Uganda", "checked_at":datetime.now(timezone.utc).isoformat(),"prices_generated_by_ai":False}
    status="failed"
    try:
        metadata=json.loads(fetcher(METADATA_URL))
        if metadata.get("success") is not True:raise ValueError("Source metadata unavailable")
        resources=[r for r in metadata["result"]["resources"] if r.get("format","").upper()=="CSV" and r.get("url","").endswith("/wfp_food_prices_uga.csv")]
        if len(resources)!=1:raise ValueError("Expected one official Uganda price CSV")
        url=resources[0]["url"];validate_url(url)
        content=fetcher(url)
        if len(content)>MAX_BYTES:raise ValueError("CSV exceeds byte limit")
        rows,summary=parse_csv(content)
        details.update(summary,sha256=hashlib.sha256(content).hexdigest(),source_url=url,records=len(rows),bytes=len(content))
        prior={(r.crop,r.market):r.payload for r in db.scalars(select(PublishedPrice))}
        model,n=auditor();details["auditor"]={"model":"IsolationForest","trees":32,"training_changes":n,"training_sha256":hashlib.sha256(ml_config().PROCESSED_FILE.read_bytes()).hexdigest(),"role":"flags changes for review; never generates prices"}
        flags=[];newer=0
        for r in rows:
            old=prior.get((r["crop"],r["market"]))
            if old and r["last_month"]<old["last_month"]:
                raise ValueError("Source regression detected; database preserved")
            if old and (r["last_month"]>old["last_month"] or r["market_price"]!=old["market_price"]):
                newer+=r["last_month"]>old["last_month"]
                change=math.log(r["market_price"]/old["market_price"])
                y,m=map(int,r["last_month"].split("-"));oy,om=map(int,old["last_month"].split("-"))
                monthly_change=change/max(1,(y-oy)*12+m-om)
                # Only compare the same source price type; transitions need review separately.
                if r["observed_price_type"] != old["observed_price_type"] or abs(change)>math.log(1.75) or model.predict([[monthly_change]])[0]==-1:
                    flags.append({"crop":r["crop"],"market":r["market"],"month":r["last_month"]})
        details["newer_series"]=newer
        if len(rows)<len(prior)*0.9:raise ValueError("Unexpected coverage loss; database preserved")
        if flags:
            status="review_required";details["flagged_series"]=flags
        elif prior and all((r["crop"],r["market"]) in prior and r["last_month"]==prior[(r["crop"],r["market"])]["last_month"] and r["market_price"]==prior[(r["crop"],r["market"])]["market_price"] for r in rows) and len(rows)==len(prior):
            status="no_new_observations"
        else:
            from app.services.published_seed import seed_published
            payload={"rows":rows,"source":ml_config().SOURCE,"generated_at":details["checked_at"],"data_end":details["latest_month"]}
            seed_published(db,settings,snapshot=payload,commit=False)
            status="published"
        db.add(SourceRefreshRun(status=status,details=details));db.commit()
    except Exception as error:
        status="failed"
        db.rollback()
        # Never retain signed download URLs or credential-like query values in an audit.
        details["error"] = (f"Source HTTP {error.code}" if isinstance(error,HTTPError)
                            else "Source network request failed" if isinstance(error,URLError)
                            else str(error)[:240] if isinstance(error,ValueError) else type(error).__name__)
        db.add(SourceRefreshRun(status="failed",details=details));db.commit()
        logging.getLogger("fairprice").warning("Source refresh failed: %s",type(error).__name__)
    finally:
        LOCK.release()
    return {"status":status,**details}
