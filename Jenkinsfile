
pipeline {
    agent any

    environment {
        AWS_REGION = 'ap-south-1'
        ECR_REPOSITORY = 'markify'
        AWS_ACCOUNT_ID = '904667240971'
        IMAGE_URI = "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPOSITORY}"
        CONTAINER_NAME = 'markify-app'
    }

    stages {
        stage('Checkout') {
            steps {
                git branch: 'main',
                    url: 'https://github.com/pratitipatlia/markify.git'
            }
        }

        stage('Install Test Dependencies') {
            steps {
                sh '''
                    python3 -m venv .venv
                    . .venv/bin/activate
                    pip install --upgrade pip
                    pip install -r requirements.txt pytest
                '''
            }
        }

        stage('Run Tests') {
            steps {
                sh '''
                    . .venv/bin/activate
                    pytest -v
                '''
            }
        }

        stage('Build Docker Image') {
            steps {
                sh '''
                    docker build -t ${ECR_REPOSITORY}:${BUILD_NUMBER} .
                    docker tag ${ECR_REPOSITORY}:${BUILD_NUMBER} ${IMAGE_URI}:${BUILD_NUMBER}
                '''
            }
        }

        stage('Push to Amazon ECR') {
            steps {
                sh '''
                    aws ecr get-login-password --region ${AWS_REGION} |
                    docker login --username AWS --password-stdin ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com

                    docker push ${IMAGE_URI}:${BUILD_NUMBER}
                '''
            }
        }

        stage('Deploy to EC2') {
            steps {
                sh '''
                    docker stop ${CONTAINER_NAME} || true
                    docker rm ${CONTAINER_NAME} || true

                    docker pull ${IMAGE_URI}:${BUILD_NUMBER}

                    docker run -d \
                      --name ${CONTAINER_NAME} \
                      --restart unless-stopped \
                      -p 5000:5000 \
                      ${IMAGE_URI}:${BUILD_NUMBER}
                '''
            }
        }

        stage('Verify Deployment') {
            steps {
                sh '''
                    sleep 5
                    curl --fail --retry 5 --retry-delay 2 http://127.0.0.1:5000/
                '''
            }
        }
    }

    post {
        always {
            sh 'docker image prune -f || true'
        }
        success {
            echo 'Markify CI/CD pipeline completed successfully!'
        }
        failure {
            echo 'Pipeline failed. Review the stage logs above.'
        }
    }
}
