set dotenv-load
set positional-arguments

PARLANT_HOME := "./cache"
LOGS_DIR := "./logs"
SERVER_ADDRESS := env("SERVER_ADDRESS", "http://localhost:8800")

setup-cache:
  mkdir -p {{PARLANT_HOME}}

@server *args: setup-cache
  PARLANT_HOME={{PARLANT_HOME}} poetry run parlant-server {{args}}

@client *args='':
  poetry run parlant -s {{SERVER_ADDRESS}} "$@"

@chat *args='':
  poetry run parlant -s {{SERVER_ADDRESS}} agent chat "$@"

@kill-server:
  lsof -i:8800 | grep :8800 | cut -d " " -f 3 | xargs kill && echo "KILLED" || echo "NOT KILLED"

@kill-test-server:
  lsof -i:8091 | grep :8091 | cut -d " " -f 3 | xargs kill && echo "KILLED" || echo "NOT KILLED"

@kill-test-plugin-server:
  lsof -i:8089 | grep :8089 | cut -d " " -f 3 | xargs kill && echo "KILLED" || echo "NOT KILLED"

@kill: kill-test-plugin-server kill-test-server
  echo "killed"

@mklogdir:
  mkdir -p {{LOGS_DIR}}

@test *tests='': mklogdir
  poetry run pytest \
    -v {{tests}} \
    --plan=initial \
    --tap-combined --tap-outdir=logs \
    --junit-xml=logs/testresults.xml \
    | tee logs/testresults.log

@test-ns *tests='': mklogdir
  poetry run pytest \
    -v {{tests}} \
    --tap-combined --tap-outdir=logs \
    --junit-xml=logs/testresults.xml \
    | tee logs/testresults.log

@test-co *tests='': mklogdir
  poetry run pytest \
    -v {{tests}} \
    --plan=initial --co \
    --tap-combined --tap-outdir=logs \
    --junit-xml=logs/testresults.xml \
    | tee logs/testresults.log

@test-ns-co *tests='': mklogdir
  poetry run pytest \
    -v {{tests}} \
    --co \
    --tap-combined --tap-outdir=logs \
    --junit-xml=logs/testresults.xml \
    | tee logs/testresults.log

@test-client:
  poetry run pytest \
    -v tests/api tests/e2e/test_client_cli_via_api.py --plan=initial

@test-client-ns:
  poetry run pytest \
    -v tests/api tests/e2e/test_client_cli_via_api.py

@install:
  clear
  poetry lock --no-update
  poetry install

@run: install server

@regen-sdk:
  python scripts/generate_client_sdk.py
