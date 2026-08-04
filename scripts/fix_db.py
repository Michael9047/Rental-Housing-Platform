"""修复数据库：补齐 properties 列 + 创建维修表 + 核心表"""
import psycopg

c = psycopg.connect('postgresql://rental:rental@localhost:5432/rental_housing')
c.autocommit = True

# ── 1. 补齐 properties 缺失列 ──
prop_cols = {
    'country': 'VARCHAR(100) DEFAULT \'CN\'',
    'unit_type_id': 'INTEGER',
    'institute_id': 'INTEGER',
    'room_number': 'VARCHAR(20)',
    'city': 'VARCHAR(100)',
    'building_block': 'VARCHAR(20)',
    'floor': 'INTEGER',
    'special_discount': 'VARCHAR(200)',
    'available_from': 'DATE',
    'min_stay_months': 'INTEGER DEFAULT 3',
    'version': 'INTEGER DEFAULT 1',
    'deleted_at': 'TIMESTAMPTZ',
    'rent_type': 'VARCHAR(20) DEFAULT \'monthly\'',
    'deposit_amount': 'INTEGER DEFAULT 1000',
    'service_fee_rate': 'FLOAT DEFAULT 0.1',
    'embedding': 'TEXT',
    'amenities': 'JSON',
    'deposit_type': 'VARCHAR(20) DEFAULT \'standard\'',
}
for col, dt in prop_cols.items():
    try:
        c.execute(f'ALTER TABLE properties ADD COLUMN IF NOT EXISTS {col} {dt}')
        print(f'  +properties.{col}')
    except Exception as e:
        print(f'  {col}: {e}')

# ── 2. 创建维修系统枚举 ──
try: c.execute("CREATE TYPE repair_issue_type AS ENUM ('plumbing','appliance','carpentry','wall_floor','plumbing_fixture','other')")
except Exception as e: print(f'repair_issue_type: {e}')
try: c.execute("CREATE TYPE repair_status AS ENUM ('pending','pending_escalated','assigned','in_progress','completed','confirmed','rejected','cancelled')")
except Exception as e: print(f'repair_status: {e}')
try: c.execute("CREATE TYPE worker_status AS ENUM ('available','working','on_leave')")
except Exception as e: print(f'worker_status: {e}')
try: c.execute("CREATE TYPE worker_scope AS ENUM ('platform','apartment')")
except Exception as e: print(f'worker_scope: {e}')

# ── 3. 创建维修工表 ──
c.execute('''CREATE TABLE IF NOT EXISTS repair_workers (
    id SERIAL PRIMARY KEY,
    user_id INTEGER UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    manager_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    status worker_status DEFAULT 'available',
    scope worker_scope DEFAULT 'apartment',
    skills JSON,
    phone VARCHAR(32) NOT NULL,
    total_jobs INTEGER DEFAULT 0,
    rating FLOAT DEFAULT 5.0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
)''')
print('  repair_workers created')

# ── 4. 创建报修工单表 ──
c.execute('''CREATE TABLE IF NOT EXISTS repair_requests (
    id SERIAL PRIMARY KEY,
    property_id INTEGER REFERENCES properties(id) ON DELETE CASCADE,
    tenant_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    landlord_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    assigned_worker_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    issue_type repair_issue_type,
    description TEXT NOT NULL,
    images JSON,
    status repair_status DEFAULT 'pending',
    scheduled_time VARCHAR(32),
    completed_at VARCHAR(32),
    work_record TEXT,
    work_images JSON,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
)''')
print('  repair_requests created')

# ── 5. 创建 bookings 表 ──
try:
    c.execute('''CREATE TABLE IF NOT EXISTS bookings (
        id SERIAL PRIMARY KEY,
        tenant_id INTEGER REFERENCES users(id),
        property_id INTEGER REFERENCES properties(id),
        landlord_id INTEGER REFERENCES users(id),
        status VARCHAR(20) DEFAULT 'pending',
        message TEXT,
        scheduled_date VARCHAR(32),
        deposit_amount INTEGER,
        service_fee INTEGER,
        deposit_status VARCHAR(20) DEFAULT 'unpaid',
        payment_transaction_id VARCHAR(255),
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
    )''')
    print('  bookings created')
except Exception as e:
    print(f'  bookings: {e}')

# ── 6. 创建 notifications 表 ──
try:
    c.execute('''CREATE TABLE IF NOT EXISTS notifications (
        id SERIAL PRIMARY KEY,
        user_id INTEGER REFERENCES users(id),
        type VARCHAR(50),
        title VARCHAR(200),
        content TEXT,
        is_read BOOLEAN DEFAULT FALSE,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
    )''')
    print('  notifications created')
except Exception as e:
    print(f'  notifications: {e}')

# ── 7. audit_logs ──
try:
    c.execute('''CREATE TABLE IF NOT EXISTS audit_logs (
        id SERIAL PRIMARY KEY,
        user_id INTEGER,
        action VARCHAR(100),
        resource_type VARCHAR(50),
        resource_id INTEGER,
        details JSON,
        ip_address VARCHAR(45),
        created_at TIMESTAMPTZ DEFAULT NOW()
    )''')
    print('  audit_logs created')
except Exception as e:
    print(f'  audit_logs: {e}')

print('DONE')
c.close()
