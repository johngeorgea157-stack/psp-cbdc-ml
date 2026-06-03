pipeline {
    agent any

    stages {
        stage('Test') {
            steps {
                sh 'python --version'
                sh 'pip install -r requirements.txt'
                sh 'pytest'
            }
        }
    }
}
