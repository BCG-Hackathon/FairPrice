import csv
import io
import json
from datetime import timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, func
from app.main import create_app
from app.config import Settings
from app.models import BuyerListing, PublishedPrice, SourceRefreshRun, utcnow
from app.services import source_refresh as service

KEY={"X-Admin-Token":"test-secret-not-default"}
URL="https://data.humdata.org/dataset/883929b1-521e-4834-97f5-0ccc2df75b89/resource/e082d683-cad5-4dcd-bf54-db76ae254d33/download/wfp_food_prices_uga.csv"


@pytest.fixture
def public_client():
    with TestClient(create_app(Settings(database_url="sqlite://",admin_token=KEY["X-Admin-Token"],buyer_registration_daily_limit=10,_env_file=None))) as client:
        yield client


def request(**changes):
    return {"name":"Test cooperative","location":"Gulu","crop":"beans","grade":"B","consent_to_listing":True,**changes}


def test_buyer_registration_is_reviewed_and_exactly_filtered(public_client):
    c=public_client
    r=c.post('/api/buyers/register',json=request()).json()
    assert r['status']=='pending'
    assert c.get('/api/buyers?crop=beans&grade=B').json()['buyers']==[]
    assert c.get('/api/buyers/pending').status_code==401
    assert c.post(f"/api/buyers/{r['id']}/review",json={'action':'approve'},headers=KEY).status_code==200
    listings=c.get('/api/buyers?crop=beans&grade=B')
    assert listings.headers['cache-control']=='no-store'
    assert len(listings.json()['buyers'])==1
    assert listings.json()['buyers'][0]['phone'] is None
    assert 'price' not in listings.json()['buyers'][0]
    assert c.get('/api/buyers?crop=beans&grade=A').json()['buyers']==[]
    assert c.get('/api/buyers?crop=maize&grade=B').json()['buyers']==[]
    c.post(f"/api/buyers/{r['id']}/review",json={'action':'withdraw'},headers=KEY)
    assert c.get('/api/buyers?crop=beans&grade=B').json()['buyers']==[]


def test_phone_consent_and_no_price_field(public_client):
    c=public_client
    assert c.post('/api/buyers/register',json=request(price=1000)).status_code==422
    assert c.post('/api/buyers/register',json=request(consent_to_listing=False)).status_code==422
    assert c.post('/api/buyers/register',json=request(crop='mango')).status_code==422
    r=c.post('/api/buyers/register',json=request(phone='+256700000000',publish_phone=False)).json()
    with c.app.state.session_factory() as db:
        assert db.get(BuyerListing,r['id']).phone is None


def test_expired_buyers_are_not_listed(public_client):
    c=public_client
    r=c.post('/api/buyers/register',json=request()).json()
    c.post(f"/api/buyers/{r['id']}/review",json={'action':'approve'},headers=KEY)
    with c.app.state.session_factory() as db:
        db.get(BuyerListing,r['id']).expires_at=utcnow()-timedelta(days=1);db.commit()
    assert c.get('/api/buyers?crop=beans&grade=B').json()['buyers']==[]


def test_registration_limit(public_client):
    for i in range(10):assert public_client.post('/api/buyers/register',json=request(name=f'Buyer {i}')).status_code==201
    assert public_client.post('/api/buyers/register',json=request()).status_code==429


@pytest.mark.parametrize('url',['http://data.humdata.org/x','https://evil.example/x','https://data.humdata.org.evil.example/x','https://data.humdata.org:444/x','https://s3.us-east-1.amazonaws.com/other-bucket/file.csv','https://data.humdata.org/private.csv'])
def test_url_security(url):
    with pytest.raises(ValueError):service.validate_url(url)


def test_official_redirect_allowed_only_for_exact_resource():
    service.validate_url('https://s3.us-east-1.amazonaws.com/hdx-production-filestore/resources/e082d683-cad5-4dcd-bf54-db76ae254d33/wfp_food_prices_uga.csv?Expires=123&Signature=abc')


class AcceptModel:
    def predict(self, values):return [1]*len(values)


def source_fixture(db, spike=False):
    cfg=service.ml_config()
    commodity={v:k for k,v in cfg.CROP_BY_COMMODITY.items()}
    output=io.StringIO();columns=['date','admin1','market','commodity','unit','currency','pricetype','price','priceflag','latitude','longitude']
    writer=csv.DictWriter(output,fieldnames=columns);writer.writeheader()
    for index,record in enumerate(db.scalars(select(PublishedPrice))):
        r=record.payload
        writer.writerow(dict(date='2026-09-15',admin1=r['district'],market=r['market'],commodity=commodity[r['crop']],unit='KG',currency='UGX',pricetype=r['observed_price_type'],price=(r['market_price']/r['market_factor'])*(10 if spike and index==0 else 1),priceflag='actual',latitude=r['latitude'],longitude=r['longitude']))
    raw=output.getvalue().encode()
    metadata=json.dumps({'success':True,'result':{'resources':[{'format':'CSV','url':URL}]}}).encode()
    return lambda url: metadata if url==service.METADATA_URL else raw


def test_valid_source_update_persists_and_survives_restart(public_client,monkeypatch):
    c=public_client;monkeypatch.setattr(service,'auditor',lambda:(AcceptModel(),5585))
    with c.app.state.session_factory() as db:
        result=service.refresh_source(db,c.app.state.settings,fetcher=source_fixture(db))
        assert result['status']=='published'
        assert db.scalar(select(SourceRefreshRun)).status=='published'
        from app.services.published_seed import seed_published
        seed_published(db,c.app.state.settings)
        assert all(r.payload['last_month']=='2026-09' for r in db.scalars(select(PublishedPrice)))
    assert c.get('/api/crops').json()['data_end']=='2026-09'
    row=c.get('/api/prices/beans').json()['rows'][0]
    assert row['forecast_month'] is None
    assert row['market_price_forecast'] is None


def test_suspicious_update_held_for_review(public_client,monkeypatch):
    c=public_client;monkeypatch.setattr(service,'auditor',lambda:(AcceptModel(),5585))
    before=c.get('/api/crops').json()['data_end']
    with c.app.state.session_factory() as db:
        result=service.refresh_source(db,c.app.state.settings,fetcher=source_fixture(db,spike=True))
        assert result['status']=='review_required'
    assert c.get('/api/crops').json()['data_end']==before


def test_failed_import_preserves_database_and_audits(public_client):
    c=public_client
    with c.app.state.session_factory() as db:
        before=db.scalar(select(func.count()).select_from(PublishedPrice))
        result=service.refresh_source(db,c.app.state.settings,fetcher=lambda url:b'{}')
        assert result['status']=='failed'
        assert db.scalar(select(func.count()).select_from(PublishedPrice))==before
    assert c.post('/api/source/refresh').status_code==401
