from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel
from typing import List, Optional, Union, Literal
from langchain_core.prompts import PromptTemplate
import os
import json
from pathlib import Path

from common.llm import my_llm
from common.path_utils import get_file_path

# ======================
# 枚举定义: 实体
# ======================
EntityType = Literal["Symptom", "Disease", "Formula", "Herb", "Effect", "Source"]

# 关系
RelationType = Literal[
    "TREATS_DISEASE",
    "ALLEVIATES_SYMPTOM",
    "HAS_EFFECT",
    "HAS_INGREDIENT",
    "HAS_SYMPTOM",
    "FROM_SOURCE"
]


# ======================
# 方剂属性定义
# ======================
class FormulaAttributes(BaseModel):
    alias: Optional[str] = None
    effect: Optional[str] = None
    indication: Optional[str] = None
    taboo: Optional[str] = None
    usage: Optional[str] = None

# 药材属性定义
class HerbAttributes(BaseModel):
    dosage: Optional[str] = None
    effect: Optional[str] = None
    indication: Optional[str] = None
    meridian: Optional[str] = None
    origin: Optional[str] = None
    place: Optional[str] = None
    processing: Optional[str] = None
    property_flavor: Optional[str] = None
    taboo: Optional[str] = None
    traits: Optional[str] = None


# ======================
# 实体与关系结构
# ======================
class Entity(BaseModel):
    name: str
    type: EntityType
    attributes: Optional[Union[FormulaAttributes, HerbAttributes]] = None

# 关系
class Relation(BaseModel):
    subject: str  # 一个实体
    subject_type: EntityType
    relation: RelationType  # 关系
    object: str # 指向另一个实体
    object_type: EntityType

# 确定实体和关系
class TCMKnowledgeGraph(BaseModel):
    entities: List[Entity]
    relations: List[Relation]


# 初始化解析器
parser = JsonOutputParser(pydantic_object=TCMKnowledgeGraph)

# 定义 Prompt
prompt = PromptTemplate(
    template=(
        "你是一个中医知识图谱抽取专家。请从以下文本中提取结构化知识：\n"
        "仅当文本中存在实体之间的明确关系时（如‘某方剂治疗某疾病’、‘某药材具有某功效’、‘方剂包含药材’等），才进行抽取。\n"
        "如果文本中仅描述单个实体的信息、未涉及其他实体或关系，请不要抽取，返回空结构：\n"
        "{{\"entities\": [], \"relations\": []}}\n\n"

        "【实体类型说明】\n"
        "- Symptom：症状，如咳嗽、腹痛等\n"
        "- Disease：疾病，如感冒、肺炎、肾虚等\n"
        "- Formula：方剂，如四君子汤、桂枝汤等\n"
        "- Herb：药材，如人参、黄芪、丁香等\n"
        "- Effect：功效，如补气、活血、祛湿、止痛等\n"
        "- Source：出处，如《本草纲目》《伤寒论》等\n\n"

        "【关系类型说明】\n"
        "- TREATS_DISEASE：方剂或药材治疗某种疾病\n"
        "- ALLEVIATES_SYMPTOM：方剂或药材缓解某种症状\n"
        "- HAS_EFFECT：方剂或药材具有某种功效\n"
        "- HAS_INGREDIENT：方剂包含某种药材\n"
        "- HAS_SYMPTOM：疾病包含某种症状\n"
        "- FROM_SOURCE：方剂出自某文献或出处\n\n"

        "若文本涉及方剂或药材，请补充对应的属性字段（如功效、性味、剂量等）。\n"
        "如果文本主要是讲方剂的，请不要抽取药材的属性字段。\n"
        "如果文本主要是讲药材的，请不要抽取方剂的属性字段。\n"
        "如果值为空null，则不必显示键的值。"
        "所有输出必须严格符合以下 JSON 格式：\n"
        "{format_instructions}\n\n"
        "输入文本：{text}"
    ),
    input_variables=["text"],
    partial_variables={"format_instructions": parser.get_format_instructions()}
)

# ======================
# 主函数封装
# ======================
def extract_tcm_knowledge(text: str):
    # 构建抽取链,提示链
    chain = prompt | my_llm | parser
    return chain.invoke({"text": text})


def extract_folder_to_outlist(folder_path: str, output_json_path: str) -> None:
    """
    遍历指定文件夹，读取每个文件内容，调用 extract_tcm_knowledge 抽取知识，
    将结果汇总为 {'out_list': [...]} 并保存为 JSON 文件。
    :param folder_path: 文件夹路径（绝对路径或相对项目根的路径）
    :param output_json_path: 输出 JSON 文件路径
    """
    folder = Path(folder_path)
    if not folder.is_dir():
        raise FileNotFoundError(f"文件夹不存在: {folder_path}")

    out_list: List[dict] = []
    files = sorted(folder.iterdir())
    for f in files:
        if not f.is_file():
            continue
        try:
            content = f.read_text(encoding="utf-8", errors="replace").strip()
        except Exception as e:
            out_list.append({"error": str(e), "file": str(f)})
            continue
        if not content:
            out_list.append({"entities": [], "relations": []})
            continue
        try:
            result = extract_tcm_knowledge(content)
            # result 为 TCMKnowledgeGraph 的 dict 形式
            out_list.append(result)
        except Exception as e:
            out_list.append({"error": str(e), "file": str(f)})

    data = {"out_list": out_list}
    out_path = Path(output_json_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fp:
        json.dump(data, fp, ensure_ascii=False, indent=2)

if __name__ == '__main__':

    # text = """
    #     九味羌活汤的药方
    #         组成
    #         羌活 防风 苍术 各9g 细辛 2g 川芎 白芷 生地黄 黄芩 甘草 各3g
    #         【方歌】
    #         九味羌活用防风，细辛苍芷与川芎，黄芩生地同甘草，分经论治宜变通。
    #         解释
    #         本方用治外感风寒湿邪，内有蕴热所致的病证。风寒束于肌表，故恶寒发热、无汗头痛；湿邪郁滞经络，气血运行不畅，故肢体酸楚疼痛；口苦微渴是兼有里热之象。治则亦以发散风寒湿邪为主，兼清里热为辅。
    #         方中 羌活 辛苦温，入太阳经，散表寒，祛风湿，利关节，止痹痛，为治风寒湿邪在表之要药。
    #         防风 长于祛风除湿，散寒止痛，为风药中之润剂； 苍术 辛苦温燥，可以发汗除湿； 防风 、 苍术 两药相合，协助 羌活 散寒除湿止痛，为臣药。
    #         细辛 性甚走窜，又搜剔筋骨之力，与 白芷 、 川芎 活血行气，祛风止痛合用以散寒祛风，宣痹以止头身之疼痛。
    #         生地 、 黄芩 清泄里热，其中生地养阴生津凉血，二者合用防止诸药辛温燥烈之性，为佐药。
    #         甘草 调和诸药而为使药。
    #         本方的配伍特点：升散药与清热药结合使用；体现了分经论治的基本结构。本方主治四时感冒风寒湿邪，表实无汗而兼有里热证者。以肢体酸楚疼痛、口苦微渴（有里热之象）为证治要点。
    #         九味羌活汤的功效
    #         功用
    #         发汗祛湿，兼清里热。
    #         主治
    #         外感风寒湿邪，兼有里热证者。恶寒发热，肌表无汗，头痛项强，肢体酸楚疼痛，口苦微渴，舌苔白或微黄，脉浮。
    #         注意
    #         治口苦 黄连 多用，是因口苦多饮胃火所致，本方中用 黄芩 是由于本方所治病症皆属上焦，故如此。
    #
    # """

    text = """
        名称
            蘅薇香，土卤，楚蘅，杜蘅，马蹄香，蘹香，杜衡葵，土细辛，钹儿草，杜葵，南细辛，马辛，马蹄细辛，泥里花，土里开花。
            杜衡的种植和炮制
            来源
            本品为马兜铃科植物杜衡Asarum forbesii Maxim.的干燥全草。
            炮制
            将原药除去泥屑等杂质，切短段，筛去灰屑。
            性状
            本品呈段状。根多，细长圆柱形，直径1.5～3mm；表面灰黄色至灰褐色，可见细纵皱纹、残留须根及须根痕；切面黄白色。根茎呈不规则结节状或圆柱形结节状，直径2～3mm，灰褐色，节明显，可见叶柄痕及根痕。叶较少，叶片多已切断，皱缩或破碎，灰绿色至褐绿色，完整者呈宽心形，顶端钝或圆，叶柄细长，灰褐色至黑褐色。质脆。气芳香，尤以根及根茎为甚，味辛、辣。
            【性味与归经】
            辛,温；有小毒。归肺、肾经。
            【功能与主治】
            祛风散寒，止痛，祛痰止咳。用于风寒头痛，关节疼痛，痰饮咳喘，外治牙痛。
            【用法与用量】
            1～3g；外用适量，研末撒患处。
            杜衡的效果
            功效
            本品为马兜铃科植物杜衡Asarum forbesii Maxim.的干燥全草。用于风寒头痛，关节疼痛，痰饮咳喘，外治牙痛。
            杜衡的药方
            ①治风寒头痛，伤风伤寒，头痛、发热初觉者：马蹄香为末，每服一钱，热酒调下，少顷饮热茶一碗，催之出汗。（《杏林摘要》香汗散）
            ②治呼吸喘息，若犹觉停滞在心胸，膈中不和者： 瓜蒂 二分，杜衡三分， 人参 一分；捣、筛，以汤服一钱匕，日二、三服。（《补缺肘后方》）
            ③治哮呴：马蹄香，焙干研为细末，每服二、三钱。如正发时，用淡醋调下，少时吐出痰涎为效。（《普济方》黑马蹄香散）
            ④治暑天发疹：杜衡根（研粉）三至四分。开水吞服。
            ⑤治损伤疼痛及蛇咬伤：杜衡（研末）每次吞服二分；外用鲜杜衡，捣敷患处。
            ⑥治蛇咬伤：杜衡根一至二钱，青蓬（菊科牡蒿）叶、竹叶细青（兰科斑叶兰）各等量， 金银花 三至四钱，野刚子（马钱科醉鱼草）五至六钱，水煎，一日三次，饭前服。
            ⑦治疮毒：杜衡根、青蓬叶各一至二钱。捣烂敷患处。（④方以下出《浙江天目山药植志》）
            ⑧治无名肿毒，瓜藤疽初起，漫肿无头，木痛不红，连贯而生：杜衡鲜叶七片，酌冲开水，炖一小时，服后出微汗，日服一次；渣捣烂加热敷贴。（《福建民间草药》）
            ⑨治蛀齿疼痛：杜衡鲜叶捻烂，塞入蛀孔中。（《福建民间草药》）
    
    """

    print(extract_tcm_knowledge(text))