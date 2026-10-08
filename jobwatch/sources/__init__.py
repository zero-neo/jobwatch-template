"""Registry of job sources. Add a module here and one line below to add a source."""
from . import greenhouse, lever

# ats name (as written in companies.yaml) -> fetch(company) -> list[Job]
REGISTRY = {
    "greenhouse": greenhouse.fetch,
    "lever": lever.fetch,
    "lever_eu": lever.fetch_eu,  # companies whose board is at jobs.eu.lever.co
}
