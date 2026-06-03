pipeline {
    agent any

    stages {
        stage('Inspect') {
            steps {
                sh 'uname -a'
                sh 'which python || true'
                sh 'which python3 || true'
                sh 'which pip || true'
                sh 'which pip3 || true'
            }
        }
    }
}
