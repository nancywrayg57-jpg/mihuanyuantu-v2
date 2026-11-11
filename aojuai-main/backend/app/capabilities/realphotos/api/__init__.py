"""HTTP router aggregate for /api/v1/realphotos."""

from fastapi import APIRouter

from . import admin_wallet, auth, contracts, gateway, jobs, me, s1, s5, s6, supplier_admin, wallet

router = APIRouter()
router.include_router(auth.router, tags=["realphotos-auth"])
router.include_router(me.router, tags=["realphotos-me"])
router.include_router(wallet.router, tags=["realphotos-wallet"])
router.include_router(admin_wallet.router, tags=["realphotos-admin"])
router.include_router(gateway.router, tags=["realphotos-gateway"])
router.include_router(jobs.router, tags=["realphotos-jobs"])
router.include_router(s1.router, tags=["realphotos-s1"])
router.include_router(s5.router, tags=["realphotos-s5"])
router.include_router(s6.router, tags=["realphotos-s6"])
router.include_router(supplier_admin.router, tags=["realphotos-supplier"])
router.include_router(contracts.router, tags=["realphotos-contracts"])
