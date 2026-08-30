"""Static catalogue for the Indian enterprise demo dataset.

Kept separate from the seeding logic so the data reads like a content
brief rather than code. Everything here is fictional: the organizations
are demo tenants inspired by an Indian retail/property context, not real
customers, and every serial number, address and advertiser is synthetic.
"""

from __future__ import annotations

# --- tenants ---------------------------------------------------------------

# Demo tenants are identified solely by these codes. The scoped reset and
# every validation query keys off them, so nothing else in the database is
# ever a candidate for deletion.
DEMO_ORG_CODES = ("RRL-DEMO", "BMR-DEMO", "USP-DEMO")

DEMO_ORGS: list[dict] = [
    {
        "code": "RRL-DEMO",
        "name": "Reliance Retail Digital Experience",
        "plan": "enterprise",
        "billing_cycle": "yearly",
        "device_target": 130,
        "domain": "rrl-demo.signage.cloud",
        "industry": "Retail",
    },
    {
        "code": "BMR-DEMO",
        "name": "BharatMart Retail Network",
        # Business caps devices at 100; seeding 88 puts this tenant at 88%
        # so the plan-usage UI has a near-limit case to show.
        "plan": "business",
        "billing_cycle": "monthly",
        "device_target": 88,
        "domain": "bharatmart-demo.signage.cloud",
        "industry": "Grocery Retail",
    },
    {
        "code": "USP-DEMO",
        "name": "UrbanSquare Properties",
        "plan": "professional",
        "billing_cycle": "yearly",
        "device_target": 40,
        "domain": "urbansquare-demo.signage.cloud",
        "industry": "Commercial Real Estate",
    },
]

# --- geography -------------------------------------------------------------

# (state, state_code, [(city, lat, lon, [(area, lat, lon), ...]), ...])
# Coordinates are real city/locality centroids so the map/geo fields are
# plausible rather than random points in the ocean.
Area = tuple[str, float, float]
City = tuple[str, float, float, list[Area]]
State = tuple[str, str, list[City]]

INDIA_GEOGRAPHY: list[State] = [
    (
        "Maharashtra",
        "MH",
        [
            (
                "Mumbai",
                19.0760,
                72.8777,
                [
                    ("Andheri", 19.1197, 72.8468),
                    ("Bandra", 19.0596, 72.8295),
                    ("Lower Parel", 18.9960, 72.8300),
                    ("Powai", 19.1176, 72.9060),
                ],
            ),
            (
                "Pune",
                18.5204,
                73.8567,
                [
                    ("Hinjawadi", 18.5913, 73.7389),
                    ("Kharadi", 18.5515, 73.9350),
                    ("Viman Nagar", 18.5679, 73.9143),
                ],
            ),
        ],
    ),
    (
        "West Bengal",
        "WB",
        [
            (
                "Kolkata",
                22.5726,
                88.3639,
                [
                    ("Salt Lake", 22.5800, 88.4200),
                    ("Park Street", 22.5530, 88.3520),
                    ("New Town", 22.5800, 88.4700),
                    ("Rajarhat", 22.6200, 88.4500),
                ],
            ),
            ("Durgapur", 23.5204, 87.3119, [("City Centre", 23.5450, 87.2800)]),
        ],
    ),
    (
        "Karnataka",
        "KA",
        [
            (
                "Bengaluru",
                12.9716,
                77.5946,
                [
                    ("Whitefield", 12.9698, 77.7500),
                    ("Koramangala", 12.9352, 77.6245),
                    ("Electronic City", 12.8452, 77.6602),
                    ("Indiranagar", 12.9784, 77.6408),
                ],
            ),
            ("Mysuru", 12.2958, 76.6394, [("Devaraja Mohalla", 12.3080, 76.6520)]),
        ],
    ),
    (
        "Telangana",
        "TG",
        [
            (
                "Hyderabad",
                17.3850,
                78.4867,
                [
                    ("Banjara Hills", 17.4126, 78.4392),
                    ("HITEC City", 17.4435, 78.3772),
                    ("Gachibowli", 17.4400, 78.3489),
                    ("Secunderabad", 17.4399, 78.4983),
                ],
            )
        ],
    ),
    (
        "Tamil Nadu",
        "TN",
        [
            (
                "Chennai",
                13.0827,
                80.2707,
                [
                    ("T Nagar", 13.0418, 80.2341),
                    ("OMR", 12.9010, 80.2279),
                    ("Anna Nagar", 13.0850, 80.2101),
                ],
            ),
            ("Coimbatore", 11.0168, 76.9558, [("RS Puram", 11.0060, 76.9490)]),
        ],
    ),
    (
        "Delhi NCR",
        "DL",
        [
            ("New Delhi", 28.6139, 77.2090, [("Connaught Place", 28.6315, 77.2167)]),
            ("Gurugram", 28.4595, 77.0266, [("Cyber Hub", 28.4959, 77.0890)]),
            ("Noida", 28.5355, 77.3910, [("Sector 18", 28.5700, 77.3260)]),
            ("Ghaziabad", 28.6692, 77.4538, [("Indirapuram", 28.6420, 77.3710)]),
        ],
    ),
]

PIN_BY_CITY: dict[str, str] = {
    "Mumbai": "400053",
    "Pune": "411057",
    "Kolkata": "700091",
    "Durgapur": "713216",
    "Bengaluru": "560066",
    "Mysuru": "570001",
    "Hyderabad": "500081",
    "Chennai": "600017",
    "Coimbatore": "641002",
    "New Delhi": "110001",
    "Gurugram": "122002",
    "Noida": "201301",
    "Ghaziabad": "201014",
}

# Commercial-style synthetic addresses — never a real private residence.
ADDRESS_TEMPLATES = [
    "Plot {n}, {area} Commercial Complex, {city}, {state} {pin}",
    "Unit {n}, {area} Business Park, {city}, {state} {pin}",
    "Shop {n}, {area} Retail Arcade, {city}, {state} {pin}",
    "Level {f}, {area} Trade Centre, {city}, {state} {pin}",
]

# In-store zones that carry a screen.
STORE_ZONES = [
    "Main Entrance",
    "Billing Area",
    "Customer Service",
    "Product Display",
    "Food Court",
    "Elevator Lobby",
    "Waiting Area",
    "Digital Kiosk Zone",
    "Outdoor Facade",
]

PROPERTY_ZONES = [
    "Tower Lobby",
    "Reception",
    "Elevator Lobby",
    "Parking Entry",
    "Amenity Deck",
    "Meeting Lobby",
]

# --- people ----------------------------------------------------------------

# Fictional demo staff. Emails use clearly synthetic demo domains.
PEOPLE: list[tuple[str, str]] = [
    ("Arjun Mehta", "arjun.mehta"),
    ("Priya Sharma", "priya.sharma"),
    ("Rahul Sen", "rahul.sen"),
    ("Sneha Iyer", "sneha.iyer"),
    ("Vikram Malhotra", "vikram.malhotra"),
    ("Neha Kapoor", "neha.kapoor"),
    ("Amit Banerjee", "amit.banerjee"),
    ("Rohan Nair", "rohan.nair"),
    ("Kavita Rao", "kavita.rao"),
    ("Sourav Mukherjee", "sourav.mukherjee"),
    ("Ananya Desai", "ananya.desai"),
    ("Karthik Subramanian", "karthik.subramanian"),
    ("Meera Joshi", "meera.joshi"),
    ("Aditya Verma", "aditya.verma"),
    ("Divya Pillai", "divya.pillai"),
    ("Rajesh Gupta", "rajesh.gupta"),
    ("Shalini Reddy", "shalini.reddy"),
    ("Nikhil Chatterjee", "nikhil.chatterjee"),
    ("Pooja Bhatt", "pooja.bhatt"),
    ("Sanjay Kulkarni", "sanjay.kulkarni"),
]

# Custom per-tenant roles layered on top of the four system roles, to show
# that tenant-defined RBAC works. (permission codes must exist in the
# platform catalogue.)
CUSTOM_ROLES: list[dict] = [
    {
        "name": "Campaign Approver",
        "description": "Reviews and approves campaigns before publishing",
        "permissions": [
            "campaigns.view", "campaigns.approve", "content.view",
            "playlists.view", "schedules.view", "notifications.view",
        ],
    },
    {
        "name": "Regional Operations Manager",
        "description": "Runs a regional fleet: devices, incidents and deployments",
        "permissions": [
            "devices.view", "devices.manage", "devices.control", "locations.view",
            "monitoring.view", "incidents.manage", "deployments.view",
            "deployments.manage", "reports.view", "notifications.view",
        ],
    },
    {
        "name": "Report Viewer",
        "description": "Read-only access to reporting and proof of play",
        "permissions": ["reports.view", "reports.export", "campaigns.view", "devices.view"],
    },
]

# --- hardware --------------------------------------------------------------

# Commercial display families. Serial prefixes are obviously synthetic.
DEVICE_MODELS: list[tuple[str, str, str, str, int, int, int]] = [
    # manufacturer, model, platform, serial prefix, width, height, panel inches
    ("LG", "55UH5N Commercial Display", "webos", "SIM-LG", 1920, 1080, 55),
    ("LG", "65UH7J Commercial Display", "webos", "SIM-LG", 3840, 2160, 65),
    ("Samsung", "QM55B Smart Signage", "tizen", "SIM-SAM", 1920, 1080, 55),
    ("Samsung", "QM65B Smart Signage", "tizen", "SIM-SAM", 3840, 2160, 65),
    ("Samsung", "QB43R Smart Signage", "tizen", "SIM-SAM", 1920, 1080, 43),
    ("BrightSign", "XT1144 Player", "android", "DEMO-AND", 1920, 1080, 49),
    ("Generic", "AndroidBox 4K Player", "android", "DEMO-AND", 3840, 2160, 75),
    ("Intel NUC", "Windows Signage Player", "windows", "DEMO-WIN", 1920, 1080, 50),
]

PLAYER_VERSIONS = ["2.3.1", "2.4.0", "2.5.0", "2.5.1"]

DEVICE_TAGS: list[tuple[str, str]] = [
    ("zone", "north"),
    ("zone", "south"),
    ("zone", "east"),
    ("zone", "west"),
    ("placement", "indoor"),
    ("placement", "outdoor"),
    ("tier", "flagship"),
    ("tier", "premium"),
    ("tier", "standard"),
    ("footfall", "high"),
    ("uptime", "24x7"),
    ("lifecycle", "new-installation"),
]

# --- content ---------------------------------------------------------------

FOLDER_TREE: dict[str, list[str]] = {
    "Marketing": ["Promotions", "Product Launches", "Seasonal"],
    "Corporate": ["Announcements", "Safety", "HR"],
    "Regional": ["East", "West", "North", "South"],
    "Archived": [],
}

# (title, asset type, folder, tags) — business-meaningful names only.
CONTENT_ITEMS: list[tuple[str, str, str, list[str]]] = [
    ("Monsoon Mega Savings Banner", "image", "Promotions", ["promotion", "seasonal"]),
    ("Monsoon Savings Showreel", "video", "Promotions", ["promotion", "seasonal"]),
    ("Festive Season Offers Banner", "image", "Seasonal", ["festival", "promotion"]),
    ("Diwali Preview Showreel", "video", "Seasonal", ["festival", "premium"]),
    ("Republic Day Celebration", "image", "Seasonal", ["festival"]),
    ("Independence Day Campaign", "image", "Seasonal", ["festival"]),
    ("Summer Collection Lookbook", "video", "Product Launches", ["product", "seasonal"]),
    ("New Product Launch Teaser", "video", "Product Launches", ["product", "new-launch"]),
    ("Smart Home Range Launch", "image", "Product Launches", ["product", "new-launch"]),
    ("Weekend Mega Sale", "image", "Promotions", ["promotion", "urgent"]),
    ("Digital Wallet Cashback Offer", "image", "Promotions", ["promotion"]),
    ("Loyalty Programme Benefits", "image", "Promotions", ["premium"]),
    ("Premium Membership Benefits", "video", "Promotions", ["premium"]),
    ("Back to School Essentials", "image", "Promotions", ["seasonal", "promotion"]),
    ("Fresh Produce Daily", "image", "Regional", ["regional"]),
    ("Store Opening Announcement", "image", "Announcements", ["corporate"]),
    ("Welcome to Our Store", "video", "Announcements", ["corporate"]),
    ("Service Counter Announcement", "image", "Announcements", ["corporate"]),
    ("Customer Safety Guidelines", "image", "Safety", ["safety", "corporate"]),
    ("Emergency Exit Information", "image", "Safety", ["safety", "urgent"]),
    ("Employee Appreciation Message", "image", "HR", ["corporate"]),
    ("Cashless Checkout Guide", "image", "Corporate", ["corporate"]),
    ("Year End Celebration", "video", "Seasonal", ["festival"]),
    ("East Zone Regional Offer", "image", "East", ["regional", "promotion"]),
    ("West Zone Regional Offer", "image", "West", ["regional", "promotion"]),
    ("North Zone Regional Offer", "image", "North", ["regional", "promotion"]),
    ("South Zone Regional Offer", "image", "South", ["regional", "promotion"]),
    ("Store Directory Board", "image", "Corporate", ["corporate"]),
    ("Weekend Footfall Highlights", "image", "Marketing", ["corporate"]),
    ("Brand Story Film", "video", "Marketing", ["premium", "corporate"]),
]

CONTENT_TAGS = [
    "promotion", "festival", "corporate", "safety", "product",
    "seasonal", "regional", "urgent", "premium", "new-launch",
]

# Ticker copy shown in marquee zones.
TICKER_MESSAGES = [
    "Today's special offer is available until 8:00 PM.",
    "Welcome to our store. Please visit the customer service desk for assistance.",
    "New arrivals are now available on the first floor.",
    "Festival offers available across selected categories.",
    "Please retain your receipt for exchange and warranty services.",
    "Digital wallet payments earn additional loyalty points this week.",
]

# --- campaigns -------------------------------------------------------------

# (name, priority) — statuses are assigned by the seeder to hit a
# realistic lifecycle distribution rather than everything being published.
CAMPAIGN_NAMES: list[str] = [
    "Monsoon Mega Savings",
    "Festive Shopping Experience",
    "Diwali Shopping Campaign",
    "Republic Day Campaign",
    "Independence Day Campaign",
    "New Product Launch",
    "Weekend Super Saver",
    "Premium Customer Campaign",
    "Store Opening — Kolkata",
    "Store Opening — Gurugram",
    "Regional Offer — West Zone",
    "Regional Offer — East Zone",
    "Regional Offer — South Zone",
    "Customer Safety Communication",
    "Back-to-School Promotion",
    "Summer Collection Showcase",
    "Year-End Celebration",
    "Loyalty Programme Drive",
    "Digital Wallet Adoption",
    "Brand Story Showcase",
    "Fresh Produce Daily Feature",
    "Weekend Footfall Booster",
]

# Realistic Indian retail dayparts.
DAYPARTS: list[tuple[str, str, str]] = [
    ("Morning", "08:00", "11:00"),
    ("Midday", "11:00", "14:00"),
    ("Afternoon", "14:00", "17:00"),
    ("Evening", "17:00", "21:00"),
    ("Late Evening", "21:00", "23:00"),
]

PLAYLIST_NAMES = [
    "Morning Store Playlist",
    "Afternoon Promotion Playlist",
    "Evening Prime-Time Playlist",
    "Weekend Promotional Playlist",
    "Corporate Information Playlist",
    "Premium Store Playlist",
    "Outdoor Advertisement Playlist",
    "Festival Campaign Playlist",
    "Emergency Information Playlist",
]

TEMPLATE_PRESETS: list[tuple[str, str]] = [
    ("Retail Promotion — Full Screen", "fullscreen"),
    ("Retail Promotion — Split Screen", "split"),
    ("Corporate Announcement", "fullscreen"),
    ("News + Ticker", "ticker"),
    ("Product Highlight", "split"),
    ("Two-Zone Promotion", "split"),
    ("Six-Zone Information Board", "grid"),
    ("Welcome Screen", "fullscreen"),
    ("Emergency Announcement", "fullscreen"),
    ("Digital Menu Board", "grid"),
]

WIDGET_PRESETS: list[tuple[str, str]] = [
    ("Store Clock", "clock"),
    ("Today's Date", "date"),
    ("City Weather", "weather"),
    ("Offers Ticker", "ticker"),
    ("Promotion Countdown", "countdown"),
    ("Loyalty QR Code", "qrcode"),
    ("Live Queue Status", "api"),
    ("Fresh Deals Feed", "rss"),
]

# --- advertising -----------------------------------------------------------

# Fictional advertisers — no real brands, no billing data.
AD_ADVERTISERS = [
    "Demo Consumer Beverages",
    "Sunrise Dairy (Demo)",
    "Demo Mobile Accessories",
    "Nirvana Wellness (Demo)",
]

# --- notifications & audit -------------------------------------------------

NOTIFICATION_TEMPLATES: list[tuple[str, str, str]] = [
    ("DEVICE_OFFLINE", "warning", "{n} displays have been offline for more than 30 minutes"),
    ("DEPLOYMENT_COMPLETED", "info", "Campaign \"{campaign}\" completed deployment"),
    ("DEPLOYMENT_FAILED", "critical", "{n} displays failed content synchronisation"),
    ("STORAGE_WARNING", "warning", "Device storage has exceeded 80% at {location}"),
    ("APPROVAL_REQUIRED", "info", "Campaign \"{campaign}\" is awaiting approval"),
    ("CAMPAIGN_EXPIRING", "warning", "Campaign \"{campaign}\" expires tomorrow"),
    ("DEVICE_REGISTERED", "info", "New display registered at {location}"),
    ("INCIDENT_RESOLVED", "info", "Offline incident resolved at {location}"),
]

AUDIT_ACTIONS: list[tuple[str, str]] = [
    ("CAMPAIGN_CREATED", "campaign"),
    ("CAMPAIGN_SUBMIT_APPROVAL", "campaign"),
    ("CAMPAIGN_APPROVED", "campaign"),
    ("CAMPAIGN_PUBLISHED", "campaign"),
    ("ASSET_UPLOADED", "asset"),
    ("ASSET_PUBLISHED", "asset"),
    ("PLAYLIST_UPDATED", "playlist"),
    ("SCHEDULE_CREATED", "schedule"),
    ("DEVICE_APPROVED", "device"),
    ("DEVICE_COMMAND_SENT", "device"),
    ("LOCATION_UPDATED", "location"),
    ("USER_INVITED", "user"),
    ("ROLE_UPDATED", "role"),
    ("API_KEY_CREATED", "api_key"),
]
