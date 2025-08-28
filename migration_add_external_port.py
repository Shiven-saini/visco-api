#!/usr/bin/env python3
"""
Database migration script to add external_port column to camera_details table.
This script adds the external_port field needed for VPN camera streaming.

Run this script once after updating the models.py file.
"""

import sys
import os
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError, ProgrammingError

# Add the app directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

from app.config.settings import settings

def run_migration():
    """Add external_port column to camera_details table if it doesn't exist."""
    
    # Create database connection
    database_url = f"postgresql://{settings.db_user}:{settings.db_password}@{settings.db_host}:{settings.db_port}/{settings.db_name}"
    engine = create_engine(database_url)
    
    try:
        with engine.connect() as conn:
            # Check if the column already exists
            check_column_query = """
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'camera_details' 
            AND column_name = 'external_port';
            """
            
            result = conn.execute(text(check_column_query))
            column_exists = result.fetchone()
            
            if column_exists:
                print("✅ Column 'external_port' already exists in camera_details table.")
                return
            
            # Add the external_port column
            add_column_query = """
            ALTER TABLE camera_details 
            ADD COLUMN external_port VARCHAR;
            """
            
            conn.execute(text(add_column_query))
            conn.commit()
            
            print("✅ Successfully added 'external_port' column to camera_details table.")
            
            # Optionally, set default external ports for existing cameras
            update_default_ports_query = """
            UPDATE camera_details 
            SET external_port = '8551' 
            WHERE external_port IS NULL;
            """
            
            conn.execute(text(update_default_ports_query))
            conn.commit()
            
            print("✅ Set default external ports (8551) for existing cameras.")
            
    except (OperationalError, ProgrammingError) as e:
        print(f"❌ Database error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False
    
    return True

if __name__ == "__main__":
    print("🔄 Running camera_details migration...")
    success = run_migration()
    
    if success:
        print("\n🎉 Migration completed successfully!")
        print("\nNext steps:")
        print("1. Restart your FastAPI application")
        print("2. Test the new VPN camera endpoints:")
        print("   - GET /cameras/vpn-streams (get all cameras with VPN URLs)")
        print("   - GET /cameras/vpn-streams/{camera_id} (get specific camera VPN URL)")
        print("\n📝 Note: When adding new cameras, you can now specify the external_port field.")
    else:
        print("\n❌ Migration failed. Please check the error messages above.")
        sys.exit(1)
