set dotenv-load
set positional-arguments

PARLANT_HOME := "./cache"
SERVER_ADDRESS := env("SERVER_ADDRESS", "http://localhost:8000")

setup-cache:
  mkdir -p {{PARLANT_HOME}}

@server *args: setup-cache
  PARLANT_HOME={{PARLANT_HOME}} poetry run parlant-server run {{args}}

@client *args='':
  poetry run parlant -s {{SERVER_ADDRESS}} "$@"

@chat *args='':
  poetry run parlant -s {{SERVER_ADDRESS}} agent chat "$@"

@validate *args: setup-cache
  PARLANT_HOME={{PARLANT_HOME}} poetry run parlant-server check {{args}}

test-ci-initial-server:
  mkdir -p logs
  poetry run pytest -v --plan=initial --tap-combined --tap-outdir=logs --capture=tee-sys --junit-xml=logs/testresults.xml | tee logs/testresults.log
  EXIT1=${PIPESTATUS[0]}
  echo $EXIT1

test: test-ci-initial-server
