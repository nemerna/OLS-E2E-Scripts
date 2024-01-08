import os
import subprocess
import requests
import json

def check_service_health(ols_base_url):
    try:
        response = requests.get(ols_base_url)
        response_data = response.json()
        expected_health_response = {"message": "This is the default endpoint for OLS", "status": "running"}
        if response_data == expected_health_response:
            return "Service is healthy"
        else:
            return "Service health check failed"
    except requests.RequestException as e:
        return f"Service health check error: {e}"




def load_prompts_from_json(file_path):
    with open(file_path, 'r') as file:
        return json.load(file)
    

def get_response_from_ols(prompt):
    ols_service_url = 'http://127.0.0.1:8080/ols'  
    response = requests.post(ols_service_url, json={"query": prompt})
    return response.json()["response"]

def extract_yaml_from_response(response):
    yaml_start_idx = response.find('apiVersion: ')
    return response[yaml_start_idx:] if yaml_start_idx != -1 else ""

def validate_with_kubeconform(yaml_content):
    # Write the YAML content to 'temp.yaml' in the current directory
    with open('temp.yaml', 'w') as file:
        file.write(yaml_content)

    # Get the current directory path
    current_directory = os.getcwd()

    # Run kubeconform using its Docker image, mounting the current directory
    result = subprocess.run(['docker', 'run', '--rm', '-v', 
                             f'{current_directory}:/data', 
                             'ghcr.io/yannh/kubeconform:latest', 
                             '-summary', '-output', 'json', '-strict', '/data/temp.yaml'], 
                            capture_output=True, text=True)

    # Process the result
    if result.returncode == 0:
        return result.stdout
    else:
        return result.stderr

def parse_kubeconform_output_and_validate_kind(validation_output, expected_kind):
    try:
        results = json.loads(validation_output)
        for resource in results['resources']:
            if 'kind' in resource and resource['kind'] != expected_kind:
                return f"Expected kind {expected_kind}, but got {resource['kind']}", False
        return "Kind matches expected value", True
    except json.JSONDecodeError:
        return "Invalid JSON output from Kubeconform", False

def validate_prompts(prompts):
    validation_results = []
    for prompt_data in prompts:
        prompt = prompt_data['prompt']
        expected_kind = prompt_data['expected_kind']
        response_text = get_response_from_ols(prompt)
        yaml_content = extract_yaml_from_response(response_text)
        kubeconform_result = validate_with_kubeconform(yaml_content)
        kind_validation_result, passed = parse_kubeconform_output_and_validate_kind(kubeconform_result, expected_kind)
        validation_results.append({
            "prompt": prompt,
            "kubeconform_result": kubeconform_result,
            "kind_validation_result": kind_validation_result,
            "passed": passed
        })
    
    # Save all results to a file for reporting
    with open('validation_report.json', 'w') as report_file:
        json.dump(validation_results, report_file, indent=4)

ols_base_url = 'http://127.0.0.1:8080'
health_check_result = check_service_health(ols_base_url)
if health_check_result != "Service is healthy":
    print(health_check_result)
    exit(1)
else:
    print("Health Check Passed")


# Load prompts and validate
subprocess.run(['docker', 'pull', 'ghcr.io/yannh/kubeconform:latest'])
prompts = load_prompts_from_json("prompts.json")
validate_prompts(prompts)
