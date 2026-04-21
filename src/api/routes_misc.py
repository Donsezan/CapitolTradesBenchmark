import asyncio
from fastapi import APIRouter, HTTPException, Request

from src.services.index_compare import POPULAR_BENCHMARKS
from src.db.repositories import TradeRepository, PoliticianRepository

router = APIRouter()


@router.get("/api/benchmarks")
async def list_benchmarks():
    return POPULAR_BENCHMARKS


@router.get("/health")
async def health(request: Request):
    db = request.app.state.db
    db_ok = db is not None
    return {"status": "ok", "db": "connected" if db_ok else "not configured"}


@router.get("/api/trades/recent")
async def recent_trades(request: Request, limit: int = 50):
    db = request.app.state.db
    repo = TradeRepository(db)
    trades = await repo.get_recent(limit=limit)
    return [t.model_dump() for t in trades]


@router.post("/api/admin/update-prices")
async def force_update_prices(request: Request):
    scheduler = request.app.state.scheduler
    if scheduler is None:
        raise HTTPException(status_code=503, detail="Scheduler not available")
    asyncio.create_task(scheduler.trigger_price_update())
    return {"status": "triggered"}


@router.get("/api/admin/debug-enrichment")
async def debug_enrichment(request: Request):
    """Show GovTrack fetch results and name match diagnostics."""
    from src.scraper.fmp_enrichment import build_lookup

    db = request.app.state.db
    pol_repo = PoliticianRepository(db)
    politicians = await pol_repo.get_all()

    loop = asyncio.get_running_loop()
    lookup, err = await loop.run_in_executor(None, build_lookup)

    if lookup is None:
        return {"error": err}

    matched, unmatched = {}, []
    for pol in politicians:
        result = lookup.get(pol.name)
        if result:
            matched[pol.name] = result
        else:
            unmatched.append(pol.name)

    return {
        "source": "govtrack.us",
        "govtrack_member_count": len(lookup.exact),
        "govtrack_names_sample": list(lookup.exact.keys())[:10],
        "db_total": len(politicians),
        "matched_count": len(matched),
        "matched": matched,
        "unmatched": unmatched,
    }


@router.post("/api/admin/enrich-parties")
async def enrich_parties(request: Request):
    """Update politician party/chamber from GovTrack current member data."""
    from src.scraper.fmp_enrichment import build_lookup

    db = request.app.state.db
    pol_repo = PoliticianRepository(db)
    politicians = await pol_repo.get_all()

    loop = asyncio.get_running_loop()
    lookup, err = await loop.run_in_executor(None, build_lookup)
    if lookup is None:
        raise HTTPException(status_code=503, detail=f"GovTrack fetch failed: {err}")

    updated = 0
    for pol in politicians:
        result = lookup.get(pol.name)
        if result and pol.id is not None:
            new_party, new_chamber = result
            if new_party != pol.party or new_chamber != pol.chamber:
                await pol_repo.update_party_chamber(pol.id, new_party, new_chamber)
                updated += 1

    return {"status": "ok", "updated": updated, "total": len(politicians)}


@router.post("/api/admin/set-parties")
async def set_parties(request: Request):
    """
    Manual party override. Body: {"mappings": {"Name": "R", "Other Name": "D", ...}}
    Useful when external APIs are unavailable.
    """
    body = await request.json()
    mappings: dict = body.get("mappings", {})
    if not mappings:
        raise HTTPException(status_code=400, detail="mappings dict required")

    db = request.app.state.db
    pol_repo = PoliticianRepository(db)
    politicians = await pol_repo.get_all()
    pol_by_name = {p.name: p for p in politicians}

    updated = 0
    not_found = []
    for name, party in mappings.items():
        if party not in ("R", "D", "I"):
            continue
        pol = pol_by_name.get(name)
        if pol and pol.id is not None:
            await pol_repo.update_party_chamber(pol.id, party, pol.chamber)
            updated += 1
        else:
            not_found.append(name)

    return {"updated": updated, "not_found": not_found}
