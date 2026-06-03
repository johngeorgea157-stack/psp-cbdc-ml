pipeline {
    agent any

    stages {
        stage('Setup Venv') {
            steps {
                sh 'python3 -m venv venv'
                sh '. venv/bin/activate && pip install -r requirements.txt'
            }
        }

        stage('Run Tests') {
            steps {
                sh '. venv/bin/activate && pytest'
            }
        }
    }
}
