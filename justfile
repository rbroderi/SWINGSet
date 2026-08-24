set shell := ["powershell.exe", "-NoLogo", "-NoProfile", "-Command"]

_default:
    @just --list

all: autopep695 ssort pyupgrade ruff basedpyright pyrefly

autopep695:
    uv run --all-extras autopep695 format .

ssort:
    uv run --all-extras ssort .

pyupgrade:
    uv run --all-extras pyupgrade --py313-plus --exit-zero-even-if-changed $((Get-ChildItem -Path . -Recurse -Filter *.py -File | Where-Object { $_.FullName -notmatch '[\\/]\.venv[\\/]' }).FullName)

basedpyright:
    uv run --all-extras basedpyright

pyrefly:
    uv run --all-extras pyrefly check --min-severity warn

ruff:
    uv run --all-extras ruff check . --fix
    uv run --all-extras ruff format --check .
