"""Miscellaneous routes: robots.txt, favicon."""
from fastapi import APIRouter
from fastapi.responses import PlainTextResponse, Response

router = APIRouter(tags=["misc"])


@router.get("/robots.txt", response_class=PlainTextResponse)
async def robots():
    return "User-agent: *\nDisallow: /\n"


@router.get("/favicon.ico")
async def favicon():
    return Response(status_code=204)
