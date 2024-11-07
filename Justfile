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

@test *tests='':
  mkdir -p logs
  poetry run pytest -v {{tests}} --plan=initial --tap-combined --tap-outdir=logs --junit-xml=logs/testresults.xml | tee logs/testresults.log

@test-ns *tests='':
  mkdir -p logs
  poetry run pytest -v {{tests}} --tap-combined --tap-outdir=logs --junit-xml=logs/testresults.xml | tee logs/testresults.log

@test-co *tests='':
  mkdir -p logs
  poetry run pytest -v {{tests}} --co  --plan=initial --tap-combined --tap-outdir=logs --junit-xml=logs/testresults.xml| tee logs/testresults.log

@test-ns-co *tests='':
  mkdir -p logs
  poetry run pytest -v {{tests}} --co  --tap-combined --tap-outdir=logs --junit-xml=logs/testresults.xml | tee logs/testresults.log
