
import os
import base64
from pathlib import Path
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

client = Groq(api_key=os.environ["GROQ_API_KEY"])
model = os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b")

image_path = Path("images/FriedChicken/001.jpg")
image_b64 = base64.b64encode(image_path.read_bytes()).decode("utf-8")

menus = [
    "ไก่ทอด", "แกงเขียวหวาน", "ข้าวมันไก่",
    "ข้าวเหนียวมะม่วง", "ก๋วยเตี๋ยวเรือ",
    "ผัดไทย", "ผัดกะเพรา", "ส้มตำ",
    "ข้าวขาหมู", "ต้มยำกุ้ง"
]

response = client.chat.completions.create(
    model=model,
    messages=[{
        "role": "user",
        "content": [
            {
                "type": "text",
                "text": (
                    "จำแนกอาหารในภาพ เลือกชื่อจากรายการนี้เท่านั้น: "
                    + ", ".join(menus)
                    + " หากระบุไม่ได้ให้ตอบ UNKNOWN "
                    "ตอบเพียงชื่อเมนูเดียว ไม่ต้องอธิบาย"
                )
            },
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{image_b64}"
                }
            }
        ]
    }],
    temperature=0.01,
    max_completion_tokens=100
)

print("Ground Truth: ไก่ทอด")
print("Prediction:", response.choices[0].message.content)
