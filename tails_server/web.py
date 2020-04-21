from aiohttp import web

from .config.defaults import DEFAULT_WEB_HOST, DEFAULT_WEB_PORT


async def index(request):
    return web.json_response({})


def start(settings):
    app = web.Application()
    app["settings"] = settings

    # Add routes
    app.add_routes([web.post("/", index)])

    web.run_app(
        app,
        host=settings.get("host") or DEFAULT_WEB_HOST,
        port=settings.get("port") or DEFAULT_WEB_PORT,
    )
