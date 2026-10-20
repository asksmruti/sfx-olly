source .env
STOP_MS="$(($(date +%s) * 1000))"
START_MS="$((STOP_MS - 2 * 24 * 60 * 60 * 1000))"


: <<<'COMMENT
curl --fail-with-body --no-buffer --request POST \
    "${SFX_STREAM_BASE_URL:-https://stream.${SFX_REALM}.signalfx.com}/v2/signalflow/execute?start=${START_MS}&stop=${STOP_MS}&resolution=60000&immediate=true" \
    --header "X-SF-Token: ${SFX_TOKEN:?Export SFX_TOKEN first}" \
    --header 'Content-Type: text/plain' \
    --header 'Accept: text/event-stream' \
    --data-binary "data('example.project.size', filter=filter('environment', 'env-test')).publish(label='A')"

COMMENT'


