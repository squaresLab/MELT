import random
import os
import requests

API_TOKEN = 'YOURTOKEN'
API_URL = "https://api-inference.huggingface.co/models/bigscience/bloom"
headers = {"Authorization": f"Bearer {API_TOKEN}"}

label_map = {"TaskName": "t-n", "DatasetName": "d-n", "HyperparameterValue": "h-v", "HyperparameterName": "h-n",
             "MetricName": "m-n", "MetricValue": "m-v", "MethodName": "mt-n", "MethodValue": "mt-v", "O": 'o'}
reverse_label_map = {v: k for k, v in label_map.items()}
ignore = ["(", ")", ":", " ", "-", "_", ",", "."]



def query(payload):
    response = requests.post(API_URL, headers=headers, json=payload)
    return response.json()


def get_label():
    input = "Q: Hello! A: "

    output = query(
        {
            "inputs": input,
            "parameters": {"max_length": 10, "temperature": 0.1, "do_sample": True},
        }
    )

    generated_text = output[0]["generated_text"]
    response_only = generated_text.split(input)[1].split(')')[0]
    return response_only


if __name__ == '__main__':
    print(get_label())