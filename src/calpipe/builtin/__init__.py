"""Built-in data source registry.  Extend by adding a module here and registering it in BUILTINS."""
from calpipe.builtin.prts import PrtsWikiSource

BUILTINS: dict[str, type] = {
    "prts_wiki": PrtsWikiSource,
}
