set dotenv-load
set positional-arguments

PARLANT_HOME := "./cache"
LOGS_DIR := "./logs"
SERVER_ADDRESS := env("SERVER_ADDRESS", "http://localhost:8000")

setup-cache:
  mkdir -p {{PARLANT_HOME}}

@server *args: setup-cache
  PARLANT_HOME={{PARLANT_HOME}} poetry run parlant-server {{args}}

@client *args='':
  poetry run parlant -s {{SERVER_ADDRESS}} "$@"

@chat *args='':
  poetry run parlant -s {{SERVER_ADDRESS}} agent chat "$@"

@kill-server:
  netstat -tulpn | grep :8000 | awk '{print $7}' | cut -d'/' -f1 | xargs kill

@kill-cli-test-server:
  lsof -i:8089 | grep 8089 | cut -d " " -f 3 | xargs kill

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

@test-client: mklogdir
  poetry run pytest \
    -v tests/e2e/test_client_cli_via_api.py \
    --plan=initial \
    --tap-combined --tap-outdir=logs \
    --junit-xml=logs/testresults.xml \
    | tee logs/testresults.log

@test-client-ns: mklogdir
  poetry run pytest \
    -v tests/e2e/test_client_cli_via_api.py \
    --tap-combined --tap-outdir=logs \
    --junit-xml=logs/testresults.xml \
    | tee logs/testresults.log
