action_name = rebalance
docker_username = ianwl
docker_image = python_algo_runtime

run:
	honcho run python . -c "main()"

clean:
	rm build/$(action_name).zip

zip: clean
	zip -r build/$(action_name).zip __main__.py simpleapi.py helper.py robinhood.py

invoke:
	bx wsk action invoke $(action_name) --blocking --result

undeploy:
	bx wsk action delete $(action_name)

build-docker:
	docker build -t $(python_algo_runtime) .

deploy:
	bx wsk action update $(action_name) --docker $(docker_username)/$(python_algo_runtime) build/$(action_name).zip -p username ${ROBINHOOD_USERNAME} -p password ${ROBINHOOD_PASSWORD} -p account ${ROBINHOOD_ACCOUNTID}

