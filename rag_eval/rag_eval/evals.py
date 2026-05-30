import os
import sys
from pathlib import Path

from dotenv import load_dotenv

dotenv_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path)

from openai import OpenAI

from ragas import Dataset, experiment
from ragas.llms import llm_factory
from ragas.metrics import DiscreteMetric

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from src.chatbot import ChatBot

openai_client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL")
)
rag_client = ChatBot()
llm = llm_factory("gpt-5.5", client=openai_client)


def load_dataset():
    dataset = Dataset(
        name="test_dataset",
        backend="local/csv",
        root_dir="evals",
    )

    data_samples = [
        {
        "question": "Gợi ý nến thơm dưới 500k",
        "grading_notes": "- gợi ý sản phẩm nến thơm\n- giá dưới 500,000 VND\n- có tên sản phẩm cụ thể",
        },
        {
        "question": "Quà sinh nhật cho bạn gái tặng gì?",
        "grading_notes": "- gợi ý quà tặng sinh nhật cho nữ\n- có thể là giftset hoặc nến thơm\n- có gợi ý sản phẩm cụ thể",
        },
        {
        "question": "Tinh dầu thư giãn có loại nào?",
        "grading_notes": "- gợi ý tinh dầu (essential oil)\n- có tên sản phẩm cụ thể\n- hướng đến mục đích thư giãn (relaxing)",
        },
        {
        "question": "Carpediem có bao nhiêu cửa hàng?",
        "grading_notes": "- trả lời được số lượng cửa hàng\n- có địa chỉ cụ thể (Hà Nội, Nha Trang, HCM)",
        },
        {
        "question": "BST Trúc Xinh gồm những sản phẩm gì?",
        "grading_notes": "- BST Trúc Xinh là bộ sưu tập chủ đề tre trúc\n- có tên sản phẩm cụ thể trong BST\n- có thể kèm giá hoặc chất liệu",
        }
    ]

    for sample in data_samples:
        row = {"question": sample["question"], "grading_notes": sample["grading_notes"]}
        dataset.append(row)

    dataset.save()
    return dataset


my_metric = DiscreteMetric(
    name="correctness",
    prompt="Check if the response contains points mentioned from the grading notes and return 'pass' or 'fail'.\nResponse: {response} Grading Notes: {grading_notes}",
    allowed_values=["pass", "fail"],
)


@experiment()
async def run_experiment(row):
    answer, results = rag_client.chat(row["question"])
    rag_client.reset_history()

    score = my_metric.score(
        llm=llm,
        response=answer,
        grading_notes=row["grading_notes"],
    )

    experiment_view = {
        **row,
        "response": answer,
        "score": score.value,
        "num_results": len(results),
    }
    return experiment_view


async def main():
    dataset = load_dataset()
    print("dataset loaded successfully", dataset)
    experiment_results = await run_experiment.arun(dataset)
    print("Experiment completed successfully!")
    print("Experiment results:", experiment_results)

    experiment_results.save()
    csv_path = Path(".") / "experiments" / f"{experiment_results.name}.csv"
    print(f"\nExperiment results saved to: {csv_path.resolve()}")


if __name__ == "__main__":
    import asyncio
    try:
        asyncio.run(main())
    finally:
        rag_client.close()
