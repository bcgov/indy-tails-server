"""
Calls to indyvdr proxy
"""

import aiohttp


class VDRProxy:
    def __init__(self, base_url):
        self.base_url = base_url

    async def get_revocation_registry_definition(self, revoc_reg_id):
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.base_url}/rev_reg_def/{revoc_reg_id}"
            ) as resp:
                return await resp.json()
