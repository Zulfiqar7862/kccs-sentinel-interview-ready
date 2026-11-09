# data/

Put the confidential workbook here (it is gitignored and never committed):

    data/KCCS_Sentinel_Reference_Data_Pack.xlsx

The API, `make demo`, the tests and `scripts/e2e_check.sh` all read it from this path by default
(override with `KCCS_WORKBOOK`). Docker Compose mounts this folder read-only at `/data`.
