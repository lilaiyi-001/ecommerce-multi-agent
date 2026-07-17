"""模拟数据生成器 — 模拟飞书 Bitable 中的商品数据"""
from __future__ import annotations
import random
import math
from app.services.category_registry import normalize_category

# ── 类目季节系数 ──────────────────────────────────────────
CATEGORY_SEASONS = {
    "食品":    {"summer_boost": 0.95, "winter_boost": 1.10, "spring_boost": 1.00, "fall_boost": 0.95},
    "服饰":    {"summer_boost": 1.10, "winter_boost": 1.20, "spring_boost": 1.05, "fall_boost": 0.75},
    "家居":    {"summer_boost": 0.90, "winter_boost": 1.10, "spring_boost": 1.05, "fall_boost": 0.95},
    "数码":    {"summer_boost": 1.15, "winter_boost": 1.05, "spring_boost": 0.95, "fall_boost": 0.85},
    "园艺":    {"summer_boost": 1.30, "winter_boost": 0.60, "spring_boost": 1.25, "fall_boost": 0.80},
    "宠物用品": {"summer_boost": 1.05, "winter_boost": 1.05, "spring_boost": 1.00, "fall_boost": 0.90},
    "文具":    {"summer_boost": 0.80, "winter_boost": 1.00, "spring_boost": 1.15, "fall_boost": 1.05},
    "箱包":    {"summer_boost": 1.10, "winter_boost": 0.95, "spring_boost": 1.05, "fall_boost": 0.90},
}

# 类目增长率
CATEGORY_GROWTH_TRENDS = {
    "食品": 0.05, "服饰": 0.03, "家居": 0.12, "数码": 0.08,
    "园艺": 0.10, "宠物用品": 0.15, "文具": 0.06, "箱包": 0.07,
}

# 成本率（成本/售价）
DEFAULT_COST_RATIOS = {
    "食品": 0.50, "服饰": 0.40, "家居": 0.50, "数码": 0.55,
    "园艺": 0.45, "宠物用品": 0.42, "文具": 0.55, "箱包": 0.45,
}

# 补货周期（天）
REORDER_DAYS = {
    "食品": 5, "服饰": 21, "家居": 10, "数码": 14,
    "园艺": 7, "宠物用品": 10, "文具": 14, "箱包": 21,
}

random.seed(42)

# ── 各类目的商品模板 ──────────────────────────────────────────
PRODUCT_TEMPLATES = {
    "食品": [
        ("新鲜红辣椒", 1.00, 4.5, 320),
        ("黄小米", 8.90, 4.7, 210),
        ("原味燕麦片", 29.90, 4.3, 450),
        ("手工荞麦面条", 15.80, 4.1, 180),
        ("冻干草莓脆", 25.00, 4.6, 390),
        ("有机黑芝麻糊", 35.00, 4.4, 260),
        ("无添加山楂条", 12.50, 4.2, 550),
        ("古法红糖姜茶", 19.90, 4.0, 310),
        ("即食燕窝银耳羹", 68.00, 4.5, 140),
        ("高蛋白鸡胸肉肠", 39.90, 4.3, 480),
    ],
    "服饰": [
        ("纯棉白色T恤", 39.90, 4.2, 680),
        ("运动速干短裤", 59.00, 4.4, 420),
        ("遮阳渔夫帽", 29.90, 4.1, 350),
        ("中筒棉袜5双装", 19.90, 4.0, 890),
        ("轻薄防晒衣", 89.00, 4.5, 560),
        ("弹力瑜伽裤", 69.00, 4.3, 720),
        ("加绒连帽卫衣", 129.00, 4.1, 310),
        ("冰丝阔腿裤", 79.00, 4.2, 480),
        ("真丝围巾礼盒", 159.00, 4.6, 180),
        ("高腰A字半身裙", 99.00, 4.0, 270),
    ],
    "家居": [
        ("不锈钢保温杯", 59.00, 4.7, 520),
        ("桌面收纳盒", 25.00, 4.3, 680),
        ("陶瓷马克杯", 35.00, 4.5, 440),
        ("长款晴雨两用伞", 49.00, 4.2, 390),
        ("记忆棉颈椎枕", 89.00, 4.4, 560),
        ("免打孔置物架", 39.00, 4.1, 730),
        ("超声波加湿器", 129.00, 4.3, 310),
        ("LED护眼台灯", 79.00, 4.5, 450),
        ("珐琅铸铁锅", 299.00, 4.6, 120),
        ("竹纤维洗碗巾10条", 15.00, 4.0, 980),
    ],
    "数码": [
        ("无线蓝牙鼠标", 49.00, 4.3, 780),
        ("快充数据线", 19.90, 4.1, 1200),
        ("手机支架", 29.00, 4.0, 650),
        ("蓝牙降噪耳机", 199.00, 4.5, 380),
        ("智能运动手环", 149.00, 4.4, 520),
        ("Type-C扩展坞", 89.00, 4.2, 290),
        ("迷你充电宝10000mAh", 79.00, 4.3, 860),
        ("无线充电板", 59.00, 4.0, 410),
        ("USB桌面小风扇", 39.00, 4.1, 950),
        ("高清摄像头", 169.00, 4.4, 210),
    ],
    "园艺": [
        ("多肉盆栽套装", 29.90, 4.4, 280),
        ("园艺工具套装", 49.00, 4.2, 190),
        ("营养土通用型", 12.00, 4.1, 520),
        ("自动浇水花盆", 39.00, 4.3, 160),
        ("园艺防刺手套", 15.00, 4.0, 340),
        ("阳台种菜盆", 25.00, 4.2, 230),
        ("缓释肥颗粒", 18.00, 4.1, 410),
        ("爬藤花架", 35.00, 4.3, 180),
        ("多肉专用颗粒土", 9.90, 4.5, 290),
        ("喷壶气压式2L", 22.00, 4.0, 560),
    ],
    "宠物用品": [
        ("宠物逗猫棒", 9.90, 4.5, 640),
        ("全封闭猫砂盆", 89.00, 4.3, 320),
        ("通用型成犬狗粮", 129.00, 4.2, 480),
        ("宠物循环饮水器", 59.00, 4.4, 290),
        ("狗狗磨牙棒零食", 25.00, 4.1, 750),
        ("猫抓板窝一体", 39.00, 4.5, 410),
        ("宠物指甲剪", 15.00, 4.0, 380),
        ("狗狗胸背牵引绳", 45.00, 4.3, 520),
        ("猫咪化毛膏", 35.00, 4.4, 360),
        ("宠物尿垫100片", 49.00, 4.2, 890),
    ],
    "文具": [
        ("笔记本记事本", 12.00, 4.3, 850),
        ("黑色中性笔盒装", 19.90, 4.1, 1200),
        ("A4资料册文件夹", 25.00, 4.2, 480),
        ("彩色便利贴", 5.00, 4.0, 1500),
        ("金属订书机", 29.00, 4.3, 320),
        ("双头马克笔24色", 35.00, 4.4, 560),
        ("网格拉链文件袋", 8.00, 4.1, 720),
        ("手账贴纸套装", 15.00, 4.5, 390),
        ("学生钢笔礼盒", 49.00, 4.2, 210),
        ("透明胶带6卷装", 9.90, 4.0, 980),
    ],
    "箱包": [
        ("帆布双肩背包", 79.00, 4.3, 460),
        ("小学生减负书包", 129.00, 4.5, 320),
        ("20寸登机箱", 299.00, 4.2, 180),
        ("户外登山双肩包", 159.00, 4.4, 240),
        ("休闲斜挎包", 69.00, 4.1, 390),
        ("笔记本电脑内胆包", 49.00, 4.3, 280),
        ("防水洗漱包", 25.00, 4.0, 560),
        ("真皮钱包男款", 189.00, 4.2, 150),
        ("妈咪包大容量", 99.00, 4.4, 210),
        ("旅行收纳袋6件套", 35.00, 4.1, 430),
    ],
    "电子产品": [
        ("Fjallraven - Foldsack No. 1 Backpack", 109.95, 4.1, 520),
        ("Mens Casual Premium Slim Fit T-Shirts", 22.30, 3.8, 680),
        ("Mens Cotton Jacket", 55.99, 4.2, 310),
        ("Mens Casual Slim Fit", 15.99, 3.6, 850),
        ("John Hardy Women 14K Gold Chain Bracelet", 695.00, 4.7, 120),
        ("Solid Gold Petite Micropave", 168.00, 3.6, 210),
        ("White Gold Plated Princess", 9.99, 3.0, 580),
        ("Pierced Owl Rose Gold Plated CZ Ring", 10.99, 3.5, 490),
        ("WD 2TB External Hard Drive", 64.99, 4.5, 4200),
        ("SanDisk 1TB Portable SSD", 59.99, 4.1, 2000),
        ("Silicon Power 256GB SSD", 29.99, 4.3, 2100),
        ("WD 4TB Gaming Drive", 114.99, 4.2, 1500),
        ("Acer SB220Q bi 21.5 Inches Monitor", 599.00, 4.2, 890),
        ("Samsung 49-Inch Curved Monitor", 999.99, 4.5, 760),
        ("BIYLACLESEN 3-in-1 Snowboard Jacket", 56.99, 2.8, 340),
        ("Lock and Love Women 3-in-1 Jacket", 29.95, 3.9, 420),
        ("Rain Jacket Women Windbreaker", 39.99, 3.9, 580),
        ("MBJ Women 3/4 Sleeve Baselayer", 9.85, 4.4, 720),
        ("Opna Women 3/4 Sleeve Tee", 7.95, 4.2, 610),
        ("DANVOUY Womens Cotton T-Shirt", 12.99, 3.8, 890),
    ],
    "服装": [
        ("Mens Casual Premium Slim Fit T-Shirts", 22.30, 3.8, 680),
        ("Mens Cotton Jacket", 55.99, 4.2, 310),
        ("Mens Casual Slim Fit", 15.99, 3.6, 850),
        ("BIYLACLESEN 3-in-1 Snowboard Jacket", 56.99, 2.8, 340),
        ("Lock and Love Women 3-in-1 Jacket", 29.95, 3.9, 420),
        ("Rain Jacket Women Windbreaker", 39.99, 3.9, 580),
        ("MBJ Women 3/4 Sleeve Baselayer", 9.85, 4.4, 720),
        ("Opna Women 3/4 Sleeve Tee", 7.95, 4.2, 610),
        ("DANVOUY Womens Cotton T-Shirt", 12.99, 3.8, 890),
        ("Suede Jacket Men Vintage", 68.00, 4.1, 230),
        ("Leather Jacket Men Classic", 129.00, 4.3, 180),
        ("Casual Hoodie Men Zip-Up", 35.99, 3.9, 450),
        ("Slim Fit Chinos Men", 42.50, 4.0, 380),
        ("Denim Jacket Women", 89.99, 4.4, 290),
        ("Floral Dress Women Summer", 45.00, 4.1, 510),
        ("Knit Sweater Women", 38.99, 3.7, 340),
        ("Polo Shirt Men Short Sleeve", 28.99, 4.0, 560),
        ("Cargo Pants Men", 49.99, 3.8, 310),
        ("Yoga Pants Women High Waist", 32.99, 4.5, 780),
        ("Sports Bra Women", 24.99, 4.2, 620),
    ],
    "珠宝首饰": [
        ("John Hardy Women 14K Gold Chain Bracelet", 695.00, 4.7, 120),
        ("Solid Gold Petite Micropave", 168.00, 3.6, 210),
        ("White Gold Plated Princess", 9.99, 3.0, 580),
        ("Pierced Owl Rose Gold Plated CZ Ring", 10.99, 3.5, 490),
        ("Gold Necklace Chain 18K", 299.00, 4.3, 160),
        ("Silver Earrings Hoop", 24.99, 4.0, 340),
        ("Diamond Engagement Ring 1ct", 2999.00, 4.8, 45),
        ("Pearl Necklace Freshwater", 89.00, 4.2, 210),
        ("Bracelet Silver Cuff", 45.00, 3.9, 280),
        ("Watch Women Quartz Crystal", 79.99, 4.1, 190),
        ("Anklet Gold Plated", 18.99, 3.8, 420),
        ("Brooch Vintage Flower", 35.00, 4.0, 150),
        ("Ring Stackable Rose Gold", 29.99, 3.9, 310),
        ("Earrings Stud Diamond Simulated", 39.99, 4.4, 250),
        ("Pendant Necklace Heart", 22.99, 3.7, 380),
        ("Chain Men Silver 30 Inch", 55.00, 4.1, 170),
        ("Cufflinks Set Gold", 68.00, 4.2, 90),
        ("Ring Sizer Adjustable", 5.99, 3.5, 520),
        ("Necklace Display Stand", 15.99, 3.6, 230),
        ("Jewelry Cleaning Cloth", 7.99, 4.0, 410),
    ],
    "家居": [
        ("Queen Size Bed Sheet Set 4-Piece", 39.99, 4.3, 1250),
        ("Non-Stick Frying Pan 12 Inch", 29.99, 4.1, 980),
        ("Memory Foam Pillow Set of 2", 34.99, 4.4, 2100),
        ("Stainless Steel Water Bottle 32oz", 18.99, 4.5, 3400),
        ("Robot Vacuum Cleaner Smart", 299.99, 4.2, 670),
        ("Glass Food Storage Containers Set", 24.99, 4.0, 890),
        ("Electric Kettle 1.7L Fast Boil", 22.99, 4.3, 1560),
        ("Bath Towels Set 6-Piece 100% Cotton", 45.99, 4.4, 1230),
        ("LED Desk Lamp Touch Control", 35.99, 4.1, 780),
        ("Wall Mounted Shelf Set 3-Pack", 28.99, 3.9, 540),
        ("Indoor Plant Artificial Ficus Tree", 42.00, 4.0, 320),
        ("Air Purifier HEPA Filter", 159.99, 4.5, 480),
        ("Slow Cooker 6 Quart Programmable", 49.99, 4.3, 910),
        ("Microwave Oven 900W 0.9 cu ft", 89.99, 4.1, 650),
        ("Blackout Curtains 84 Inch Set of 2", 32.99, 4.4, 1150),
        ("Knife Set 15-Piece Kitchen Block", 79.99, 4.2, 430),
        ("Stand Mixer 5.5 Quart 660W", 249.99, 4.6, 290),
        ("Smart LED Light Bulb WiFi", 14.99, 4.0, 2100),
        ("Electric Toothbrush Sonic", 44.99, 4.3, 680),
        ("Vacuum Insulated Thermos 40oz", 27.99, 4.4, 920),
    ],
    "运动户外": [
        ("Yoga Mat Premium 6mm Thick", 29.99, 4.5, 2300),
        ("Adjustable Dumbbell Set 50lb", 199.99, 4.3, 560),
        ("Jump Rope Speed Cable", 12.99, 4.2, 3450),
        ("Resistance Bands Set 5-Pack", 19.99, 4.4, 4200),
        ("Foam Roller High Density 36 Inch", 25.99, 4.1, 1250),
        ("Running Shoes Men Lightweight", 89.99, 4.3, 890),
        ("Cycling Bike Indoor Stationary", 349.99, 4.2, 340),
        ("Protein Powder Whey 2lb Chocolate", 44.99, 4.5, 2100),
        ("Sport Watch GPS Heart Rate", 199.99, 4.1, 670),
        ("Kettlebell Cast Iron 35lb", 39.99, 4.3, 480),
        ("Insulated Water Bottle 24oz", 16.99, 4.0, 3100),
        ("Boxing Gloves Training 12oz", 34.99, 4.2, 580),
        ("Pilates Ball Exercise 65cm", 22.99, 3.8, 720),
        ("Treadmill Folding Compact", 599.99, 4.1, 230),
        ("Swim Goggles Anti-Fog UV", 14.99, 4.0, 1560),
        ("Tennis Racket Carbon Fiber", 129.99, 4.4, 310),
        ("Camping Tent 4 Person Waterproof", 169.99, 4.2, 190),
        ("Ab Roller Wheel Knee Pad", 18.99, 3.9, 1100),
        ("Weighted Vest 20lb Adjustable", 79.99, 4.0, 340),
        ("Massage Gun Deep Tissue", 89.99, 4.4, 670),
    ],
}


def _build_product(category: str, idx: int, base: tuple, rng: random.Random) -> dict:
    """根据模板元组构建完整商品字典，含成本、库存等衍生字段"""
    title, price, rating, reviews = base
    cost_ratio = DEFAULT_COST_RATIOS.get(category, 0.50)
    cost_price = round(price * cost_ratio * (0.9 + rng.random() * 0.2), 2)
    stock_pct = 0.3 + rng.random() * 0.7
    max_stock = max(1, int(reviews * (0.5 + rng.random() * 1.5)))
    stock_level = max(1, int(max_stock * stock_pct))
    reorder_days = REORDER_DAYS.get(category, 14)
    safety_stock = max(1, int(max_stock * 0.15))
    reorder_point = max(1, int(reorder_days * max_stock / 30 + safety_stock))
    sales = round(reviews * (rng.gauss(0.08, 0.03)), 0)
    sales = max(1, sales)
    seasonal = CATEGORY_SEASONS.get(category, {}).get("summer_boost", 1.0) - 1.0
    growth = CATEGORY_GROWTH_TRENDS.get(category, 0.05)

    return {
        "product_id": idx + abs(hash(category + str(idx))) % 10000,
        "title": title,
        "price": round(price, 2),
        "cost_price": cost_price,
        "rating_rate": round(min(5.0, rating + rng.gauss(0, 0.05)), 1),
        "rating_count": reviews,
        "avg_daily_sales": sales,
        "max_stock": max_stock,
        "stock_level": stock_level,
        "reorder_point": reorder_point,
        "safety_stock": safety_stock,
        "seasonal_factor": round(seasonal + rng.gauss(0, 0.02), 3),
        "growth_trend": growth,
        "category": category,
    }


def get_demo_products(category: str, count: int = 20) -> list[dict]:
    """获取指定类目的模拟商品数据"""
    category = normalize_category(category)
    products = PRODUCT_TEMPLATES.get(category, [])
    result = []
    for i, base in enumerate(products[:count], 1):
        result.append(_build_product(category, i, base, random))
    return result


def get_category_list() -> list[str]:
    """获取可用类目列表（标准中文类目名）"""
    from app.services.category_registry import get_standard_categories
    std = get_standard_categories()
    return [c for c in std if c in PRODUCT_TEMPLATES]


# ── 历史销量 ──────────────────────────────────────────────
def get_historical_sales(product_id: int, base_daily: float = 30, days: int = 90) -> list[dict]:
    """生成某个商品的历史日销量数据"""
    rng = random.Random(product_id)
    weekly_pattern = [1.2, 1.0, 0.9, 0.9, 1.0, 1.1, 1.3]
    trend = rng.uniform(-0.3, 0.4)

    data = []
    for d in range(days):
        trend_factor = 1 + trend * (d / days)
        weekday = d % 7
        week_factor = weekly_pattern[weekday]
        noise = rng.gauss(0, base_daily * 0.12)
        value = max(1, base_daily * trend_factor * week_factor + noise)
        month = (d // 30) + 1
        day_of_month = (d % 30) + 1
        data.append({
            "day": d + 1,
            "date": f"2025-{month:02d}-{day_of_month:02d}",
            "sales": round(value, 1),
        })
    return data


# ── 用户行为 ──────────────────────────────────────────────
def generate_user_behavior(category: str, num_users: int = 150) -> list[dict]:
    """生成某个类目的模拟用户行为数据"""
    rng = random.Random(abs(sum(ord(c) for c in category)) % (2**31))
    templates = PRODUCT_TEMPLATES.get(category, PRODUCT_TEMPLATES["电子产品"])

    behaviors = []
    for uid in range(1, num_users + 1):
        ur = random.Random(uid * 1000 + hash(category))
        num_views = ur.randint(3, 15)

        for idx in range(min(num_views, len(templates))):
            title, price, rating, reviews = templates[idx]
            hour = ur.randint(8, 23)

            behaviors.append({
                "user_id": f"user_{uid:04d}", "product_idx": idx,
                "behavior": "view", "price": price, "hour": hour,
                "category": category, "title": title,
            })
            if ur.random() < 0.30:
                behaviors.append({
                    "user_id": f"user_{uid:04d}", "product_idx": idx,
                    "behavior": "cart", "price": price, "hour": hour,
                    "category": category, "title": title,
                })
                if ur.random() < 0.40:
                    behaviors.append({
                        "user_id": f"user_{uid:04d}", "product_idx": idx,
                        "behavior": "purchase", "price": price, "hour": hour,
                        "category": category, "title": title,
                    })
    return behaviors


# ── 竞品价格数据 ──────────────────────────────────────────
def get_competitor_prices(category: str, product_id: int) -> dict:
    """生成某个商品的竞品价格模拟数据"""
    products = get_demo_products(category, count=20)
    target = None
    for p in products:
        if p["product_id"] == product_id:
            target = p
            break
    if not target:
        target = products[0]

    rng = random.Random(product_id)
    base = target["price"]
    competitors = []
    for i in range(3 + rng.randint(1, 4)):
        comp_price = round(base * (0.7 + rng.random() * 0.6), 2)
        comp_rating = round(3.0 + rng.random() * 2.0, 1)
        comp_sales = max(1, int(target.get("rating_count", 100) * (0.3 + rng.random() * 1.5)))
        competitors.append({
            "competitor_id": i + 1000 + product_id,
            "name": f"Competitor Brand {chr(65 + i)} {target['title'][:20]}",
            "price": comp_price,
            "rating": comp_rating,
            "monthly_sales": comp_sales,
        })

    market_avg = round(sum(c["price"] for c in competitors) / len(competitors), 2)
    return {
        "target_product_id": target["product_id"],
        "target_product_title": target["title"],
        "target_price": target["price"],
        "market_avg_price": market_avg,
        "price_position": "above" if target["price"] > market_avg else "below",
        "competitors": competitors,
    }
