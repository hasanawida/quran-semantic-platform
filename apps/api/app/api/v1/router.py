from fastapi import APIRouter

from app.api.v1 import (
    admin_morphology,
    admin_versions,
    ai,
    auth,
    export,
    meta,
    methodology,
    morphology,
    projects,
    quran,
    review,
    roots,
    scholarship,
)

router = APIRouter()
router.include_router(auth.router)
router.include_router(meta.router)
router.include_router(methodology.router)
router.include_router(quran.router)
router.include_router(roots.router)
router.include_router(morphology.router)
router.include_router(scholarship.router)
router.include_router(projects.router)
router.include_router(review.router)
router.include_router(export.router)
router.include_router(ai.router)
router.include_router(admin_versions.router)
router.include_router(admin_morphology.router)
