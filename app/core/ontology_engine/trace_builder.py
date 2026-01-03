#trace_builder.py
import logging
import json

trace_logger = logging.getLogger("eligibility_trace")
trace_logger.setLevel(logging.INFO)

handler = logging.FileHandler("logs/eligibility_trace.log")
handler.setFormatter(logging.Formatter('%(message)s'))
trace_logger.addHandler(handler)


def build_trace(trial_id, inclusion, exclusion, overall):
    trace = {
        "trial_id": trial_id,
        "overall": overall,
        "inclusion": inclusion,
        "exclusion": exclusion
    }

    trace_logger.info(json.dumps(trace, indent=2))
    return trace
