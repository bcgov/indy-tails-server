from aiohttp import web

from .config.defaults import DEFAULT_WEB_HOST, DEFAULT_WEB_PORT


async def index(request):
    return web.json_response({})


def start(host=None, port=None):

    if not host:
        host = DEFAULT_WEB_HOST

    if not port:
        port = DEFAULT_WEB_PORT

    app = web.Application()

    # Add routes
    app.add_routes([web.get("/", index)])

    web.run_app(app, host=host, port=port)
