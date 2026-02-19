FROM node:22-alpine

WORKDIR /app

# Install dependencies based on the preferred package manager
COPY package.json package-lock.json* ./
RUN npm install

COPY . .

# Build Arguments for Next.js (baked into the client at build time)
ARG NEXT_PUBLIC_AZURE_CLIENT_ID
ARG NEXT_PUBLIC_AZURE_TENANT_ID
ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_AZURE_CLIENT_ID=$NEXT_PUBLIC_AZURE_CLIENT_ID
ENV NEXT_PUBLIC_AZURE_TENANT_ID=$NEXT_PUBLIC_AZURE_TENANT_ID
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

# Build the Next.js application
RUN npm run build

# Expose the listening port
EXPOSE 3000

# Start the application
CMD ["npm", "start"]
