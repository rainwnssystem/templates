-- S3 Sink
%flink.ssql

INSERT INTO `sink_s3`
SELECT
    COUNT(*) AS temperature_count,
    AVG(temperature) AS avg_temperature,
    window_start,
    window_end
FROM TABLE(
    TUMBLE(TABLE device, DESCRIPTOR(event_ts), INTERVAL '1' MINUTE)
)
GROUP BY window_start, window_end

-- Select Test (not sink)
%flink.ssql(type=update)
SELECT
    COUNT(*) AS temperature_count,
    AVG(temperature) AS avg_temperature,
    window_start,
    window_end
FROM TABLE(
    TUMBLE(TABLE device, DESCRIPTOR(event_ts), INTERVAL '5' SECONDS)
)
GROUP BY window_start, window_end;

---

SELECT window_start, window_end, SUM(`size`) AS total_size
FROM TABLE(HOP(TABLE acclog, DESCRIPTOR(`time`), INTERVAL '15' SECOND, INTERVAL '30' SECOND))
GROUP BY window_start, window_end;

---

SELECT window_start, window_end, SUM(`size`) AS total_size
FROM TABLE(CUMULATE(TABLE acclog, DESCRIPTOR(`time`), INTERVAL '10' SECOND, INTERVAL '30' SECOND))
GROUP BY window_start, window_end;