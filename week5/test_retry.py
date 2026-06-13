from tenacity import retry,stop_after_attempt,wait_exponential
import random

attempt_count=0
@retry(stop=stop_after_attempt(5),wait=wait_exponential(multiplier=0.1,min=0.1,max=1))
def flaky_function():
    global attempt_count
    attempt_count+=1
    print(f"Attempt {attempt_count}")
    if attempt_count<3:
        raise ConnectionError("Simulated failure")
    return "Success!"
result=flaky_function()
print(f"\nResult:{result}")