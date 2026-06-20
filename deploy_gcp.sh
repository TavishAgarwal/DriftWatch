#!/bin/bash
set -e

# Generate a unique project ID
PROJECT_ID="driftwatch-$(date +%s)"
BILLING_ACCOUNT="015646-FA5C86-358112"
REGION="us-central1"

echo "Creating GCP Project: $PROJECT_ID..."
gcloud projects create $PROJECT_ID --name="Driftwatch"

echo "Linking billing account..."
gcloud billing projects link $PROJECT_ID --billing-account=$BILLING_ACCOUNT

echo "Setting default project..."
gcloud config set project $PROJECT_ID

echo "Enabling APIs (this takes about 1-2 minutes)..."
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com

echo "Deploying Backend..."
# Deploy backend
gcloud run deploy driftwatch-backend \
  --source ./backend \
  --region $REGION \
  --allow-unauthenticated \
  --project $PROJECT_ID \
  --format="value(status.url)" > backend_url.txt

BACKEND_URL=$(cat backend_url.txt)
echo "Backend successfully deployed at: $BACKEND_URL"

echo "Building and Pushing Frontend Image with injected Backend URL..."
gcloud builds submit . \
  --config cloudbuild.yaml \
  --substitutions=_API_URL=$BACKEND_URL \
  --project $PROJECT_ID

echo "Deploying Frontend..."
gcloud run deploy driftwatch-frontend \
  --image gcr.io/$PROJECT_ID/driftwatch-frontend \
  --region $REGION \
  --allow-unauthenticated \
  --project $PROJECT_ID \
  --format="value(status.url)" > frontend_url.txt

FRONTEND_URL=$(cat frontend_url.txt)
echo "Frontend successfully deployed at: $FRONTEND_URL"

echo ""
echo "=== DEPLOYMENT COMPLETE ==="
echo "Frontend URL: $FRONTEND_URL"
echo "Backend URL:  $BACKEND_URL"
