from pydantic import BaseModel


class StatsOut(BaseModel):
    farmers: int
    factories: int
    transporters: int
    transporters_waiting_approval: int
    live_jobs: int  # not yet settled, rejected or disputed
    jobs_settled: int
    orders: int
    tonnes_diverted: float
    escrow_held: int  # paisa funded for jobs that are not finished
    open_escalations: int
