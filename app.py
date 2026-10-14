"""Nouriva food-classification demo.

Place this file beside models/best_model_clean.pth, then run:
    python -m streamlit run app.py

The checkpoint must contain model_state_dict and ordered class_names.
Preprocessing follows the loader discussed earlier: Resize(256),
CenterCrop(224), ToTensor, and ImageNet normalization.
"""

from pathlib import Path

import streamlit as st
import torch
from PIL import Image, ImageOps, UnidentifiedImageError
from torchvision import models, transforms


MODEL_PATH = Path(__file__).resolve().parent / "models" / "best_model_clean.pth"


@st.cache_resource(show_spinner="กำลังโหลดโมเดลอาหาร…")
def load_model(model_path: str, modified_ns: int):
    """Cache the model, reloading when the checkpoint file changes."""
    checkpoint = torch.load(model_path, map_location="cpu", weights_only=True)
    if not isinstance(checkpoint, dict):
        raise ValueError("ไฟล์โมเดลต้องมี model_state_dict และ class_names")

    architecture = checkpoint.get("architecture", "efficientnet_b0")
    if architecture != "efficientnet_b0":
        raise ValueError(f"ไฟล์นี้ใช้ {architecture} แต่แอปรองรับ efficientnet_b0")

    class_names = checkpoint.get("class_names")
    if (
        not isinstance(class_names, (list, tuple))
        or not class_names
        or any(not isinstance(name, str) or not name.strip() for name in class_names)
        or len(set(class_names)) != len(class_names)
    ):
        raise ValueError(
            "ไม่พบ class_names ที่ถูกต้องในไฟล์โมเดล "
            "ต้องใช้ชื่อคลาสเรียงตามลำดับตอนฝึกโมเดล"
        )

    state_dict = checkpoint.get("model_state_dict")
    if not isinstance(state_dict, dict):
        raise ValueError("ไม่พบ model_state_dict ในไฟล์โมเดล")

    model = models.efficientnet_b0(weights=None)
    model.classifier[1] = torch.nn.Linear(
        model.classifier[1].in_features, len(class_names)
    )
    model.load_state_dict(state_dict, strict=True)
    model.eval()

    preprocess = transforms.Compose(
        [
            transforms.Resize(256),
            transforms.CenterCrop(224),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225],
            ),
        ]
    )
    return model, tuple(class_names), preprocess


def predict(image, model, class_names, preprocess):
    tensor = preprocess(image).unsqueeze(0)
    with torch.inference_mode():
        probabilities = torch.softmax(model(tensor), dim=1)[0]
    scores, indices = probabilities.topk(min(3, len(class_names)))
    return [
        {"menu": class_names[index], "score": score}
        for index, score in zip(indices.tolist(), scores.tolist())
    ]


def main():
    st.set_page_config(page_title="Nouriva | ทดลองจำแนกอาหาร", page_icon="🍽️")
    st.title("🍽️ Nouriva")
    st.write("อัปโหลดรูปอาหาร แล้วดูว่าโมเดลทำนายเป็นเมนูอะไร")
    st.caption("ใช้ภาพใหม่ที่ไม่ได้อยู่ในชุดฝึก เพื่อทดลองการจำแนกอาหาร")

    if not MODEL_PATH.is_file():
        st.error("ยังไม่พบไฟล์โมเดล")
        st.write("วางไฟล์ best_model_clean.pth ในโฟลเดอร์ models ที่อยู่ข้าง app.py")
        st.code(str(MODEL_PATH), language=None)
        return

    try:
        model, class_names, preprocess = load_model(
            str(MODEL_PATH), MODEL_PATH.stat().st_mtime_ns
        )
    except Exception as error:
        st.error("โหลดโมเดลไม่สำเร็จ")
        with st.expander("รายละเอียดข้อผิดพลาด", expanded=True):
            st.exception(error)
        return

    st.success(f"พร้อมทดลอง • รองรับ {len(class_names)} เมนู")
    with st.expander("เมนูที่โมเดลรู้จัก"):
        for name in class_names:
            st.write(f"• {name}")

    uploaded = st.file_uploader(
        "เลือกรูปอาหาร", type=["jpg", "jpeg", "png", "webp"]
    )
    if uploaded is None:
        st.info("เริ่มด้วยรูปอาหาร 1 รูป โดยเลือกเมนูจากรายการที่โมเดลรู้จัก")
        return

    try:
        uploaded.seek(0)
        with Image.open(uploaded) as original:
            food_image = ImageOps.exif_transpose(original).convert("RGB")
    except (UnidentifiedImageError, OSError, ValueError) as error:
        st.error(f"อ่านรูปไม่ได้: {error}")
        return

    st.image(food_image, caption=uploaded.name, width="stretch")
    try:
        with st.spinner("กำลังจำแนกอาหาร…"):
            predictions = predict(food_image, model, class_names, preprocess)
    except Exception as error:
        st.error("ทำนายภาพไม่สำเร็จ")
        st.exception(error)
        return

    best = predictions[0]
    st.subheader("ผลการทำนาย")
    st.metric("เมนูที่โมเดลเลือก", best["menu"])
    st.metric("คะแนนโมเดล (Softmax)", f"{best['score'] * 100:.2f}%")
    st.caption(
        "คะแนนนี้เป็นคะแนนจากโมเดล ไม่ได้ยืนยันว่าทายถูก "
        "ภาพเมนูอื่นก็อาจถูกทายเป็นหนึ่งในเมนูที่โมเดลรู้จัก"
    )
    st.write("เมนูที่ได้คะแนนสูงสุด 3 อันดับ")
    st.table(
        [
            {"อันดับ": rank, "เมนู": item["menu"], "คะแนน": f"{item['score'] * 100:.2f}%"}
            for rank, item in enumerate(predictions, start=1)
        ]
    )


if __name__ == "__main__":
    main()
