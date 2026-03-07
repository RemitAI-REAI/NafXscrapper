from tenacity import stop_after_attempt, wait_fixed, wait_exponential, Retrying

def with_retry(func):
    return Retrying(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=0),
    ).wraps(func)