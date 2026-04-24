#!/bin/sh

# Default to UID 1000 if PUID/PGID not set
USER_ID=${PUID:-1000}
GROUP_ID=${PGID:-1000}

# Create group if it doesn't exist
if ! getent group "$GROUP_ID" >/dev/null; then
    echo "Creating group for GID $GROUP_ID"
    groupadd -g "$GROUP_ID" appgroup
fi

# Create user if it doesn't exist
if ! getent passwd "$USER_ID" >/dev/null; then
    echo "Creating user for UID $USER_ID"
    useradd -u "$USER_ID" -g "$GROUP_ID" -m appuser
fi

# Get the actual user/group names
USER_NAME=$(getent passwd "$USER_ID" | cut -d: -f1)
GROUP_NAME=$(getent group "$GROUP_ID" | cut -d: -f1)

echo "Correcting permissions for data directories (UID: $USER_ID, GID: $GROUP_ID)..."
mkdir -p /app/wiki /app/sources /app/snapshots /app/archive /app/schema
chown -R "$USER_ID:$GROUP_ID" /app/wiki /app/sources /app/snapshots /app/archive /app/schema

echo "Starting application as $USER_NAME..."
exec gosu "$USER_ID:$GROUP_ID" "$@"
