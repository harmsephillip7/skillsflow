#!/bin/bash

# SkillsFlow Deployment Script
# This script helps deploy to Vercel with Neon PostgreSQL

echo "=========================================="
echo "SkillsFlow Production Deployment"
echo "=========================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if we're in the right directory
if [ ! -f "manage.py" ]; then
    echo -e "${RED}Error: Run this script from the skillsflow directory${NC}"
    exit 1
fi

# Step 1: Collect static files
echo -e "\n${YELLOW}Step 1: Collecting static files...${NC}"
python manage.py collectstatic --noinput

# Step 2: Check Vercel CLI
echo -e "\n${YELLOW}Step 2: Checking Vercel CLI...${NC}"
if ! command -v vercel &> /dev/null; then
    echo -e "${RED}Vercel CLI not found. Installing...${NC}"
    npm install -g vercel
fi

echo -e "${GREEN}Vercel CLI is installed${NC}"

# Step 3: Deploy to Vercel
echo -e "\n${YELLOW}Step 3: Deploying to Vercel...${NC}"
echo "Make sure you have set the following environment variables in Vercel:"
echo "  - DATABASE_URL (your Neon PostgreSQL connection string)"
echo "  - DJANGO_SECRET_KEY (generate a secure key)"
echo "  - DEBUG=False"
echo "  - ALLOWED_HOSTS=.vercel.app,your-domain.com"
echo ""

read -p "Have you configured the Vercel environment variables? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    vercel --prod
else
    echo -e "${YELLOW}Please configure environment variables first:${NC}"
    echo "1. Go to https://vercel.com/your-project/settings/environment-variables"
    echo "2. Add the required variables"
    echo "3. Re-run this script"
fi

echo -e "\n${GREEN}=========================================="
echo "Deployment process completed!"
echo "==========================================${NC}"
