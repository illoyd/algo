# Docker info
docker_username = ianwl
docker_image = python_algo_runtime

# Action and Trigger info
action_name = rebalance
trigger_name = weekday-ten-thirty

run:
	honcho run python . -c "main()"

clean:
	rm build/$(action_name).zip

zip: clean
	zip -r build/$(action_name).zip *.py

invoke:
	bx wsk action invoke $(action_name) --blocking --result

undeploy:
	bx wsk action delete $(action_name)

build-docker:
	docker build -t $(docker_image) . \
	&& docker tag $(docker_image) $(docker_username)/$(docker_image) \
	&& docker push $(docker_username)/$(docker_image)

deploy: zip
	bx wsk action update $(action_name) --docker $(docker_username)/$(docker_image) build/$(action_name).zip -p username ${ROBINHOOD_USERNAME} -p password ${ROBINHOOD_PASSWORD} -p account ${ROBINHOOD_ACCOUNTID} -p execute true

create-trigger: delete-trigger
	# Create a trigger to run at 10:30 EST (15:30 UTC)
	bx wsk trigger create $(trigger_name) \
		--feed /whisk.system/alarms/alarm \
    --param cron "0 30 15 * * 1-5"
    # --param maxTriggers 1

create-rule: delete-rule
	# Bind the trigger to the action
	bx wsk rule create \
    $(trigger_name)-$(action_name) \
    $(trigger_name) \
    $(action_name)

delete-trigger:
	bx wsk trigger delete $(trigger_name)

delete-rule:
	bx wsk rule delete $(trigger_name)-$(action_name)
