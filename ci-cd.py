import os
from git import Repo, InvalidGitRepositoryError
import subprocess
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

logs = ""
isCommandProcessed = False

def append_to_logs(log):
    global logs
    logs += log + "\n"
    print(logs)

def is_maven_project(project_path):
    return os.path.exists(os.path.join(project_path, 'pom.xml'))

def is_gradle_project(project_path):
    gradle_files = ['build.gradle', 'build.gradle.kts']
    return any(os.path.exists(os.path.join(project_path, file)) for file in gradle_files)

def detect_build_system(project_path):
    if is_maven_project(project_path):
        return "Maven"
    elif is_gradle_project(project_path):
        return "Gradle"
    else:
        return "Unknown"

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/logs')
def get_logs():
    global isCommandProcessed
    print("Returning Logs")
    return jsonify({'logs': logs, 'isCommandProcessed': isCommandProcessed})

def run_command(command):
    try:
        global isCommandProcessed
        result = subprocess.run(command, shell=True, capture_output=True, text=True, check=True)
        append_to_logs(result.stdout)
    except subprocess.CalledProcessError as e:
        # Handle command failure
        append_to_logs(f"Error: {e}")
        append_to_logs(e.stderr)
        isCommandProcessed = True
        raise

@app.route('/build-and-deploy', methods=['POST'])
def build_and_deploy():
    global logs
    global isCommandProcessed
    repo_url = request.json.get('repo_url')
    repo_path = request.json.get('repo_path')
    branch = request.json.get('branch')
    username = request.json.get('username')
    password = request.json.get('password')
    project = request.json.get('project')
    print("Deploying and building")

    home_directory = os.path.expanduser("~")

    repo_path = os.path.join(home_directory, repo_path)
    try:
        if not os.path.exists(repo_path):
            append_to_logs(f"Creating directory: {repo_path}")
            os.makedirs(repo_path)
            Repo.clone_from(repo_url, repo_path, branch=branch)
            append_to_logs("Repo cloned")
        else:
            append_to_logs("Repo already exists. Pulling latest changes.")
            repo = Repo(repo_path)
            origin = repo.remote('origin')
            origin.pull(branch)
    except InvalidGitRepositoryError:
        append_to_logs("Invalid Git repository error.")
        return jsonify({'status': 'error', 'logs': logs})

    build_system = detect_build_system(repo_path)

    if build_system == "Maven":
        run_command(f'cd {repo_path} && mvn clean package')
    elif build_system == "Gradle":
        run_command(f'cd {repo_path} && ./gradlew clean build')
    else:
        append_to_logs("Unknown build system. Cannot proceed.")
        return jsonify({'status': 'error', 'logs': logs})

    run_command(f'docker build -t {project} {repo_path}')
    run_command(f'docker run -p 8080:8080 {project}')
    isCommandProcessed = True

    return jsonify({'status': 'success', 'logs': logs})

if __name__ == '__main__':
    app.run(debug=True)
