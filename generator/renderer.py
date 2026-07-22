from pathlib import Path
from hashlib import sha256
from html import escape
import re
import shutil

from jinja2 import Environment, FileSystemLoader, select_autoescape

from config import ASSETS_DIR, OUTPUT_DIR, TEMPLATES_DIR
from generator.page_type import PageType


class Renderer:
    HOME_SUBJECT_SHORTCUTS = [
        (
            "영어과외",
            "subject-english",
            "영어 학습이 필요하다면 먼저 거주 지역을 선택한 뒤 가까운 지역 페이지에서 세부 정보를 확인하세요.",
        ),
        (
            "수학과외",
            "subject-math",
            "수학은 학교 진도와 학생 수준의 차이가 커서 지역별 학습 환경을 함께 살펴보는 것이 좋습니다.",
        ),
        (
            "국어과외",
            "subject-korean",
            "국어 학습은 독해, 문법, 내신 준비 방향이 달라 지역과 학교 흐름을 함께 확인하면 도움이 됩니다.",
        ),
        (
            "과학과외",
            "subject-science",
            "과학은 학년과 단원에 따라 필요한 설명 방식이 달라 가까운 지역 페이지부터 탐색하는 편이 자연스럽습니다.",
        ),
    ]

    READING_PATTERNS = [
        ("tip", "summary", "faq"),
        ("checklist", "quote"),
        ("tip", "quote", "checklist"),
        ("summary", "tip"),
        ("checklist", "faq"),
        ("quote", "tip", "summary"),
        ("tip", "checklist"),
        ("summary", "quote", "faq"),
        ("faq", "tip", "checklist"),
        ("quote", "summary"),
    ]

    TIP_BANK = {
        "region": [
            "{title}는 이동 동선과 수업 가능 시간을 함께 맞춰야 꾸준히 이어가기 좋습니다.",
            "{title}를 볼 때는 첫 상담에서 학생의 오답 원인을 어떻게 파악하는지 확인해 보세요.",
            "{title}에서는 학교 일정과 학원 시간을 함께 놓고 무리 없는 주간 계획을 잡는 것이 중요합니다.",
            "{title} 선택 전에는 수업 후 피드백 방식이 문자, 노트, 과제표 중 무엇인지 확인하는 편이 좋습니다.",
            "{title}는 단기 성적보다 매주 반복 가능한 학습 루틴을 만드는지가 핵심입니다.",
            "{title} 상담에서는 학생이 어려워하는 단원을 먼저 말하게 하면 수업 방향이 더 빨리 잡힙니다.",
            "{title}는 집 근처 수업이라도 집중 시간이 맞지 않으면 효과가 떨어질 수 있습니다.",
            "{title}를 비교할 때는 비용보다 수업 후 복습 관리가 얼마나 구체적인지 먼저 살펴보세요.",
        ],
        "school": [
            "{title}는 학교별 시험 범위와 수행평가 일정을 함께 확인해야 준비가 안정적입니다.",
            "{title} 대비에서는 최근 시험에서 반복된 단원과 서술형 비중을 먼저 보는 것이 좋습니다.",
            "{title} 학생은 학교 진도와 개인 약점을 분리해서 관리해야 과제가 밀리지 않습니다.",
            "{title} 수업은 내신 기간 전후로 복습 강도를 다르게 조절하는 방식이 효과적입니다.",
            "{title}는 학교 수업 노트와 프린트 관리가 성적 관리의 출발점이 될 수 있습니다.",
            "{title} 상담 때는 학생이 실제로 틀린 시험지나 오답노트를 함께 보는 편이 좋습니다.",
        ],
        "subject": [
            "{title}는 개념 설명 후 바로 유형 연습으로 연결되는지 확인하면 수업 품질을 가늠하기 쉽습니다.",
            "{title} 학습은 많이 푸는 것보다 틀린 이유를 짧게 정리하는 습관이 더 중요할 때가 많습니다.",
            "{title}는 단원별 난이도 차이가 크기 때문에 쉬운 부분과 어려운 부분을 따로 관리해야 합니다.",
            "{title} 수업에서는 숙제 양보다 다음 수업에서 오답을 어떻게 다시 확인하는지가 중요합니다.",
            "{title}는 기초 개념이 흔들리면 심화 문제로 갈수록 시간이 크게 늘어날 수 있습니다.",
            "{title}를 시작할 때는 최근 시험지나 문제집 표시를 기준으로 약점을 정리해 보세요.",
        ],
        "grade": [
            "{title}는 학년 변화에 따라 공부량보다 공부 순서를 먼저 조정하는 것이 좋습니다.",
            "{title} 시기에는 생활 리듬과 과제 처리 속도를 함께 관리해야 부담이 줄어듭니다.",
            "{title} 학생은 한 번에 많은 계획을 세우기보다 지킬 수 있는 최소 루틴을 만드는 편이 좋습니다.",
            "{title}는 다음 학기 진도보다 현재 놓친 개념을 먼저 회복해야 안정적으로 올라갈 수 있습니다.",
            "{title} 상담에서는 학생이 혼자 공부할 때 멈추는 지점을 구체적으로 확인해 보세요.",
            "{title}는 시험 기간과 평상시 학습 방식을 다르게 설계해야 오래 유지됩니다.",
        ],
        "default": [
            "{title}는 학생의 현재 수준을 정확히 보는 것에서 출발해야 합니다.",
            "{title}를 선택할 때는 수업 방식과 복습 방식이 함께 맞는지 확인하세요.",
            "{title}는 일정 관리와 과제 피드백이 분명할수록 꾸준히 이어가기 쉽습니다.",
            "{title}는 학생이 스스로 설명할 수 있는 단계까지 확인하는 과정이 필요합니다.",
            "{title}는 상담에서 목표 점수보다 현재 습관을 먼저 보는 편이 현실적입니다.",
            "{title}는 짧은 기간에도 약점 단원을 분명히 나누면 방향을 잡기 쉽습니다.",
        ],
    }

    FAQ_BANK = {
        "region": [
            ("{title}를 고를 때 가장 먼저 볼 점은 무엇인가요?", "학생의 현재 수준, 이동 동선, 수업 후 피드백 방식을 함께 확인하는 것이 좋습니다."),
            ("{title}는 주 몇 회가 적당한가요?", "학습 공백이 크면 주 2회 이상, 유지 관리가 목적이면 주 1회부터 시작해도 됩니다."),
            ("{title} 상담 전에 준비할 자료가 있나요?", "최근 시험지, 오답노트, 사용하는 문제집을 준비하면 학생 상태를 더 정확히 볼 수 있습니다."),
            ("{title}는 온라인 수업과 병행할 수 있나요?", "가능하지만 학생 집중도와 과목 특성에 따라 대면 수업과 역할을 나누는 편이 안정적입니다."),
            ("{title} 비용보다 중요한 기준은 무엇인가요?", "수업 후 복습, 숙제 점검, 오답 피드백이 실제로 이어지는지 확인하는 것이 중요합니다."),
        ],
        "school": [
            ("{title} 대비는 언제 시작하는 게 좋나요?", "시험 3~4주 전에는 범위 확인과 약점 정리를 시작하는 편이 좋습니다."),
            ("{title} 내신 대비에서 중요한 자료는 무엇인가요?", "학교 프린트, 필기, 최근 시험지, 수행평가 안내가 핵심 자료입니다."),
            ("{title} 학생에게 과외가 필요한 시점은 언제인가요?", "진도는 따라가지만 시험에서 실수가 반복될 때 맞춤 점검이 도움이 됩니다."),
            ("{title} 수업은 학교 진도에 맞춰 진행되나요?", "대부분 학교 진도를 기준으로 하되 부족한 선행 개념을 함께 보완합니다."),
            ("{title} 대비는 과목별로 다르게 봐야 하나요?", "과목마다 출제 방식이 달라 개념, 유형, 서술형 준비 비중을 다르게 잡는 것이 좋습니다."),
        ],
        "subject": [
            ("{title}는 개념부터 다시 해야 하나요?", "최근 오답이 개념 부족인지 유형 미숙인지 먼저 구분한 뒤 범위를 정하는 것이 좋습니다."),
            ("{title} 성적이 빨리 오르지 않는 이유는 무엇인가요?", "문제 양보다 오답 원인 분석과 반복 복습이 부족한 경우가 많습니다."),
            ("{title} 수업에서 숙제는 얼마나 필요한가요?", "학생이 감당할 수 있는 양을 꾸준히 끝내고 다음 수업에서 확인하는 것이 중요합니다."),
            ("{title}는 선행과 복습 중 무엇이 먼저인가요?", "기초가 흔들리면 복습이 먼저이고, 안정적이면 학교 진도보다 조금 앞서가도 됩니다."),
            ("{title} 오답 관리는 어떻게 해야 하나요?", "틀린 문제를 다시 푸는 것에서 끝내지 말고 틀린 이유를 짧게 분류해야 합니다."),
        ],
        "grade": [
            ("{title}는 어떤 학습 습관이 중요하나요?", "매일 짧게라도 과제를 끝내고 오답을 다시 보는 루틴이 중요합니다."),
            ("{title} 시기에 과목을 늘려도 괜찮나요?", "핵심 과목의 기본 루틴이 잡힌 뒤 필요한 과목을 추가하는 편이 안정적입니다."),
            ("{title}는 시험 대비를 언제 시작해야 하나요?", "평상시에는 진도와 복습을 나누고 시험 3주 전부터 범위 중심으로 전환하는 것이 좋습니다."),
            ("{title} 학생이 자주 무너지는 부분은 무엇인가요?", "계획은 세우지만 끝까지 확인하지 못하는 경우가 많아 점검 구조가 필요합니다."),
            ("{title}는 선행이 꼭 필요한가요?", "현재 개념과 문제 풀이가 안정적일 때 선행 효과가 커집니다."),
        ],
        "default": [
            ("{title} 상담에서 무엇을 확인해야 하나요?", "학생 수준, 목표, 수업 방식, 복습 관리 방법을 함께 확인하는 것이 좋습니다."),
            ("{title}는 얼마나 지나야 변화가 보이나요?", "학습 공백과 과목에 따라 다르지만 보통 루틴이 잡히는 데 몇 주가 필요합니다."),
            ("{title}에서 가장 중요한 관리는 무엇인가요?", "오답을 다시 확인하고 다음 공부로 연결하는 피드백 관리가 중요합니다."),
            ("{title}는 학생 성향에 맞출 수 있나요?", "설명 속도, 숙제량, 점검 방식을 학생 상황에 맞게 조절하는 것이 좋습니다."),
            ("{title}를 오래 유지하려면 무엇이 필요하나요?", "무리한 계획보다 지킬 수 있는 공부 흐름을 만드는 것이 핵심입니다."),
        ],
    }

    CHECKLIST_BANK = {
        "region": ["학생 수준 확인", "이동 시간 확인", "수업 장소 조율", "복습 관리 방식 확인"],
        "school": ["학교 특성 확인", "시험 범위 확인", "내신 대비 계획", "수행평가 일정 점검"],
        "subject": ["개념 이해 확인", "유형 연습 계획", "오답 분석", "단원별 약점 정리"],
        "grade": ["학년별 목표 설정", "생활 리듬 점검", "과제 루틴 만들기", "시험 기간 계획"],
        "default": ["현재 수준 확인", "학습 계획 수립", "복습 관리", "피드백 방식 점검"],
    }

    SUMMARY_BANK = {
        "region": [
            ("지역 조건 점검", "이동 동선과 수업 시간을 현실적으로 맞춥니다."),
            ("학습 루틴 설계", "학생이 꾸준히 지킬 수 있는 반복 구조를 만듭니다."),
            ("피드백 관리", "수업 후 오답과 과제를 확인할 기준을 정합니다."),
            ("목표 조정", "현재 수준과 시험 일정을 함께 보고 목표를 잡습니다."),
        ],
        "school": [
            ("학교 자료 분석", "프린트, 필기, 시험지를 중심으로 범위를 정리합니다."),
            ("내신 대비", "출제 경향과 서술형 대비를 함께 준비합니다."),
            ("진도 동기화", "학교 진도와 개인 약점을 분리해 관리합니다."),
            ("시험 루틴", "시험 전후 복습 강도를 다르게 조절합니다."),
        ],
        "subject": [
            ("개념 정리", "핵심 개념을 설명할 수 있는지 먼저 확인합니다."),
            ("유형 훈련", "자주 틀리는 유형을 반복 가능한 방식으로 묶습니다."),
            ("오답 분석", "실수, 개념 부족, 시간 부족을 구분합니다."),
            ("복습 연결", "다음 수업에서 다시 확인할 기준을 남깁니다."),
        ],
        "grade": [
            ("학년 목표", "현재 학년에 맞는 현실적인 목표를 세웁니다."),
            ("습관 관리", "매일 이어갈 수 있는 최소 루틴을 만듭니다."),
            ("과목 균형", "중요 과목과 보완 과목의 시간을 나눕니다."),
            ("성장 점검", "점수뿐 아니라 태도와 지속성을 함께 확인합니다."),
        ],
        "default": [
            ("수준 진단", "현재 이해도와 약점을 먼저 파악합니다."),
            ("계획 수립", "학생에게 맞는 순서로 공부 흐름을 만듭니다."),
            ("복습 관리", "수업 이후 다시 볼 내용을 분명히 정리합니다."),
            ("성과 확인", "작은 변화가 이어지는지 주기적으로 점검합니다."),
        ],
    }

    TYPE_GROUPS = {
        PageType.PROVINCE: "region",
        PageType.CITY: "region",
        PageType.DISTRICT: "region",
        PageType.DONG: "region",
        PageType.SCHOOL: "school",
        PageType.SUBJECT: "subject",
        PageType.GRADE: "grade",
    }

    PAGE_TYPE_GUIDANCE = {
        PageType.PROVINCE: [
            "{title}에서는 지역별 교육 환경 차이를 먼저 이해하면 과외 선택 기준이 더 분명해집니다.",
            "{title}는 시군구마다 학교 분포와 통학 시간이 달라 학습 계획도 다르게 잡는 것이 좋습니다.",
            "{title} 학생은 거주 지역과 학교 위치를 함께 고려해야 수업 시간이 안정적으로 유지됩니다.",
            "{title}에서는 내신 준비와 이동 동선을 함께 보는 가정이 많습니다.",
            "{title}의 학습 환경은 도시 규모, 학교 밀집도, 학원 접근성에 따라 차이가 생깁니다.",
            "{title}를 비교할 때는 지역 이름보다 학생에게 맞는 수업 관리 방식을 먼저 확인해야 합니다.",
            "{title}에서는 시험 기간 이동 부담을 줄이는 수업 방식이 꾸준함에 도움이 됩니다.",
            "{title} 학습 계획은 학교 일정과 가정 내 공부 시간을 함께 놓고 조정하는 편이 현실적입니다.",
            "{title}는 넓은 지역 특성상 같은 과목이라도 수업 가능 조건이 크게 달라질 수 있습니다.",
            "{title}에서는 학년 변화에 따라 과목 우선순위를 다시 정리하는 과정이 필요합니다.",
            "{title} 학생에게는 단기 보강보다 반복 가능한 복습 루틴이 더 중요할 때가 많습니다.",
            "{title} 상담에서는 학생의 현재 수준과 지역별 수업 가능 범위를 함께 확인하는 것이 좋습니다.",
            "{title}는 학교군과 생활권이 달라 같은 시도 안에서도 학습 분위기가 다르게 형성됩니다.",
            "{title}에서 과외를 찾을 때는 수업 장소, 시간, 피드백 방식이 모두 맞아야 오래 유지됩니다.",
            "{title} 학생은 시험 범위가 넓어질수록 오답 정리와 일정 관리가 성적에 큰 영향을 줍니다.",
            "{title}에서는 학습 공백을 먼저 좁힌 뒤 선행이나 심화로 넘어가는 흐름이 안정적입니다.",
            "{title}의 교육 환경은 지역별 선택지가 다양한 만큼 기준을 좁혀 비교하는 것이 중요합니다.",
            "{title}는 학생 성향과 생활 리듬을 반영해야 실제 공부 시간으로 이어집니다.",
            "{title}에서는 학부모가 관리 부담을 줄일 수 있도록 수업 후 확인 기준을 정하는 것이 좋습니다.",
            "{title}는 지역이 넓기 때문에 가까운 수업보다 지속 가능한 수업인지가 더 중요할 수 있습니다.",
        ],
        PageType.CITY: [
            "{title}는 학교와 생활권이 맞물려 있어 학생별 통학 환경을 함께 보는 것이 좋습니다.",
            "{title} 학생은 학교 일정, 학원 시간, 가정 학습 시간을 함께 조정해야 무리가 적습니다.",
            "{title}에서는 중등과 고등으로 올라갈수록 내신 대비 방식이 달라집니다.",
            "{title}의 학교 분포를 고려하면 과목별 보강 시점도 더 현실적으로 잡을 수 있습니다.",
            "{title}는 학생이 실제로 집중할 수 있는 시간대를 찾는 것이 중요합니다.",
            "{title}에서는 시험 기간 전에 약한 단원을 미리 분리해 두면 준비 부담이 줄어듭니다.",
            "{title} 학습 계획은 학교 진도와 개인 약점을 분리해서 관리할수록 효과적입니다.",
            "{title} 학생에게는 과제 양보다 매주 확인 가능한 복습 구조가 필요합니다.",
            "{title}에서는 같은 시 안에서도 동별 이동 거리와 수업 가능 시간이 달라질 수 있습니다.",
            "{title} 선택은 단순 거리보다 수업 후 피드백이 꾸준히 이어지는지가 중요합니다.",
            "{title}는 학년별 시험 난이도 차이를 고려해 공부 순서를 조정해야 합니다.",
            "{title} 학생은 내신과 수행평가 일정을 함께 관리하면 공부 흐름이 안정됩니다.",
            "{title}에서는 학교별 출제 경향을 확인하고 오답 유형을 누적 관리하는 방식이 도움이 됩니다.",
            "{title} 상담에서는 최근 시험지와 문제집 사용 상태를 함께 보는 것이 좋습니다.",
            "{title}의 학습 환경은 지역 생활권에 따라 저녁 시간 집중도에도 차이가 생깁니다.",
            "{title} 학생은 공부 시간을 늘리기보다 무엇을 먼저 끝낼지 정하는 과정이 필요합니다.",
            "{title}에서는 학부모와 학생이 확인할 목표를 다르게 두면 관리가 쉬워집니다.",
            "{title}는 수업 내용보다 수업 후 학생이 무엇을 다시 볼지 남기는 과정이 중요합니다.",
            "{title}는 학교가 많은 지역일수록 내신 대비 기준을 더 구체적으로 잡아야 합니다.",
            "{title} 학생에게 맞는 수업은 설명 속도와 과제 난이도를 함께 조절합니다.",
        ],
        PageType.DISTRICT: [
            "{title}는 같은 시 안에서도 학교군과 생활권이 달라 학습 환경을 따로 살펴야 합니다.",
            "{title} 학생은 주변 학교 일정과 이동 시간을 고려해 수업 계획을 잡는 것이 좋습니다.",
            "{title}에서는 내신 기간에 수업 시간을 무리하게 늘리기보다 복습 단위를 작게 나누는 방식이 효과적입니다.",
            "{title}는 학생이 자주 틀리는 단원을 빠르게 파악하는 데서 시작합니다.",
            "{title}의 교육 환경은 동별 학교 접근성과 방과 후 일정에 영향을 받습니다.",
            "{title} 학생에게는 과목별 약점을 분리해 관리하는 수업이 도움이 됩니다.",
            "{title}에서는 시험 범위가 확정되기 전부터 기본 개념을 정리해 두는 것이 좋습니다.",
            "{title} 상담에서는 학교 진도와 학생의 실제 이해도를 따로 확인해야 합니다.",
            "{title}는 같은 구 안에서도 수업 장소에 따라 이동 부담이 달라질 수 있습니다.",
            "{title} 학생은 오답을 다시 풀 수 있는 상태로 남기는 복습 방식이 필요합니다.",
            "{title}에서는 수행평가와 지필고사를 함께 고려해 주간 계획을 세우는 것이 좋습니다.",
            "{title}는 학습 습관이 무너지는 시간대를 피해서 배치하면 효율이 높아집니다.",
            "{title} 학생은 진도 보강과 시험 대비를 같은 방식으로 진행하면 부담이 커질 수 있습니다.",
            "{title}에서는 학교별 평가 방식에 맞춰 서술형과 객관식 대비 비중을 조절해야 합니다.",
            "{title} 선택 시에는 수업 후 과제 확인 방식이 구체적인지 살펴보는 편이 좋습니다.",
            "{title}는 학습 선택지가 다양한 만큼 학생에게 맞지 않는 방식도 빠르게 걸러야 합니다.",
            "{title} 학생은 매주 같은 기준으로 학습 변화를 확인하면 성취감이 쌓입니다.",
            "{title}에서는 짧은 복습이라도 반복되게 만드는 것이 장기 성적에 도움이 됩니다.",
            "{title}는 성적표보다 실제 풀이 과정을 함께 보는 상담이 더 정확합니다.",
            "{title}는 지역 생활 리듬을 반영한 계획일수록 유지 가능성이 높습니다.",
        ],
        PageType.DONG: [
            "{title}는 주변 학교와 생활 동선을 함께 살펴야 수업 시간이 안정적으로 맞습니다.",
            "{title} 학생은 가까운 수업보다 꾸준히 복습이 이어지는 수업인지 확인하는 것이 좋습니다.",
            "{title}에서는 방과 후 이동 시간이 짧아도 피로도를 고려해 수업 강도를 조절해야 합니다.",
            "{title}는 학생의 실제 공부 장소와 집중 시간을 함께 정하면 유지하기 쉽습니다.",
            "{title}의 학습 환경은 주변 학교 일정과 가정 학습 분위기에 영향을 받습니다.",
            "{title} 학생은 내신 대비 전부터 오답 유형을 모아두면 시험 준비가 덜 급해집니다.",
            "{title}에서는 과목별로 공부 순서를 다르게 잡아야 학습 부담이 줄어듭니다.",
            "{title} 상담에서는 최근 시험지, 교재 표시, 숙제 패턴을 함께 보는 것이 좋습니다.",
            "{title}는 같은 동 안에서도 학교와 집 위치에 따라 가능한 수업 시간이 달라질 수 있습니다.",
            "{title} 학생에게는 매주 확인 가능한 작은 목표가 공부 습관을 만드는 데 도움이 됩니다.",
            "{title}에서는 학생이 혼자 공부할 때 막히는 지점을 먼저 찾아야 합니다.",
            "{title}는 설명을 듣는 시간보다 수업 후 다시 해보는 시간이 더 중요할 수 있습니다.",
            "{title} 학생은 시험 기간에 새 문제만 늘리기보다 약한 단원을 좁혀 보는 편이 좋습니다.",
            "{title}에서는 학부모 확인이 부담이 되지 않도록 간단한 피드백 기준을 정하는 것이 좋습니다.",
            "{title}는 학생 성향에 맞춰 과제량과 복습 속도를 조절해야 오래 갑니다.",
            "{title}는 주변 학습 선택지가 많아도 학생에게 맞는 방식은 따로 확인해야 합니다.",
            "{title} 학생은 학교 수업 이해와 시험 적용 사이의 간격을 줄이는 연습이 필요합니다.",
            "{title}에서는 생활 리듬이 흔들릴 때를 대비해 최소 학습 루틴을 만들어 두는 것이 좋습니다.",
            "{title}는 단기 점수보다 다음 시험에도 이어지는 공부 방식을 남기는 것이 중요합니다.",
            "{title}는 가까운 지역 정보와 함께 과목·학년별 페이지를 비교하면 선택 기준이 선명해집니다.",
        ],
        PageType.SCHOOL: [
            "{title}는 학교별 시험 범위와 평가 방식에 맞춰 내신 대비 방향을 잡는 것이 중요합니다.",
            "{title} 학생은 수업 필기, 프린트, 최근 시험지를 함께 정리해야 준비가 정확해집니다.",
            "{title} 내신은 학교 진도와 학생의 약점을 분리해서 관리할 때 안정됩니다.",
            "{title} 시험 대비는 범위가 나오기 전부터 기본 개념을 정리해 두는 편이 좋습니다.",
            "{title} 학생에게는 수행평가 일정과 지필고사 준비를 함께 보는 계획이 필요합니다.",
            "{title}는 학교 수업에서 놓친 부분을 다시 설명하고 바로 적용하는 흐름이 중요합니다.",
            "{title}에서는 서술형 비중과 반복 출제 단원을 먼저 확인하면 준비 방향이 선명해집니다.",
            "{title} 학생은 틀린 문제를 유형별로 나누어 다음 시험 전에 다시 확인해야 합니다.",
            "{title} 내신 준비는 교과서, 프린트, 문제집 순서를 무작정 섞지 않는 것이 좋습니다.",
            "{title}는 시험 직전보다 평상시 복습 관리가 더 큰 차이를 만들 수 있습니다.",
            "{title} 학생은 학교 과제를 끝내는 것과 시험에 필요한 이해를 구분해야 합니다.",
            "{title} 상담에서는 실제 시험지와 오답노트를 함께 보는 것이 가장 현실적입니다.",
            "{title}에서는 학기 초부터 약한 과목의 복습 시간을 따로 확보하는 것이 좋습니다.",
            "{title} 학생은 내신 기간에 과목별 우선순위를 정하지 않으면 준비가 쉽게 분산됩니다.",
            "{title} 시험 대비는 암기와 문제 풀이를 분리하지 않고 확인 순서로 연결해야 합니다.",
            "{title}에서는 점수 변화뿐 아니라 오답이 줄어드는 과정을 함께 확인해야 합니다.",
            "{title} 학생은 시험이 끝난 뒤 틀린 단원을 다시 정리해야 다음 범위가 덜 부담스럽습니다.",
            "{title}는 학교별 자료를 기준으로 진행될 때 수업 활용도가 높아집니다.",
            "{title} 내신은 학생이 설명할 수 있는 개념과 풀 수 있는 문제의 차이를 줄이는 과정입니다.",
            "{title}는 학습 계획, 복습, 시험 대비가 한 흐름으로 이어질 때 성적 관리가 안정됩니다.",
        ],
        PageType.SUBJECT: [
            "{title}는 개념 이해, 유형 연습, 오답 분석 순서가 흐트러지지 않아야 합니다.",
            "{title} 학습은 먼저 핵심 개념을 설명할 수 있는지 확인하는 과정이 필요합니다.",
            "{title}에서는 응용 문제로 넘어가기 전 기본 유형을 안정적으로 끝내야 합니다.",
            "{title} 학생은 틀린 문제를 다시 푸는 것보다 왜 틀렸는지 분류하는 습관이 중요합니다.",
            "{title}는 단원별 난이도 차이가 크기 때문에 약한 단원을 따로 관리해야 합니다.",
            "{title}는 숙제량보다 다음 수업에서 오답을 어떻게 확인하는지가 중요합니다.",
            "{title} 학습 순서는 학생의 현재 이해도와 시험 일정에 맞춰 조정해야 합니다.",
            "{title}에서는 실수가 반복되는 문제를 따로 모아 복습 주기를 만드는 것이 좋습니다.",
            "{title} 학생은 개념은 아는데 문제에 적용하지 못하는 구간을 집중적으로 봐야 합니다.",
            "{title}는 선행보다 현재 단원의 빈틈을 먼저 메우는 것이 효과적일 때가 많습니다.",
            "{title} 공부는 긴 시간보다 짧게 여러 번 확인하는 복습이 도움이 됩니다.",
            "{title}에서는 문제 풀이 속도보다 정확한 풀이 과정을 먼저 안정시켜야 합니다.",
            "{title} 학생은 단순 암기와 이해가 필요한 내용을 구분해 공부해야 합니다.",
            "{title} 상담에서는 최근 오답과 교재 진행 상태를 함께 확인하는 것이 좋습니다.",
            "{title}는 유형별 접근 방법을 정리하면 시험장에서 흔들림이 줄어듭니다.",
            "{title}에서는 어려운 문제보다 자주 틀리는 기본 문제를 먼저 잡아야 합니다.",
            "{title} 학습은 수업 중 이해와 혼자 복습할 때의 재현 가능성을 함께 봐야 합니다.",
            "{title} 학생은 오답을 누적하지 않도록 다음 수업 전에 다시 확인하는 과정이 필요합니다.",
            "{title}는 개념, 응용, 복습이 연결될 때 성적 변화가 더 안정적으로 나타납니다.",
            "{title} 공부 방법은 학생 성향에 맞춰 설명 방식과 문제 난이도를 조절해야 합니다.",
        ],
        PageType.GRADE: [
            "{title}는 학년별 목표를 현실적으로 잡고 공부 습관을 먼저 안정시키는 것이 중요합니다.",
            "{title} 학생은 시험 준비와 평상시 복습을 다른 방식으로 운영해야 합니다.",
            "{title}에서는 과목별 공부 시간을 정하기보다 먼저 약한 과목의 원인을 나누어 봐야 합니다.",
            "{title} 학습 전략은 생활 리듬과 과제 처리 속도를 함께 고려해야 유지됩니다.",
            "{title}는 학년이 올라갈수록 개념 이해와 문제 적용 사이의 간격이 커질 수 있습니다.",
            "{title} 학생에게는 매주 끝낼 수 있는 최소 목표가 공부 습관을 만드는 데 도움이 됩니다.",
            "{title}에서는 시험 범위가 넓어지기 전에 복습 단위를 작게 나눠두는 것이 좋습니다.",
            "{title}는 현재 학년의 빈틈과 다음 학년 준비를 균형 있게 봐야 합니다.",
            "{title} 학생은 선행보다 현재 단원의 이해가 흔들리는지 먼저 확인해야 합니다.",
            "{title}는 공부 시간이 늘어도 오답 정리가 없으면 성적 변화가 더딜 수 있습니다.",
            "{title}에서는 학생이 혼자 공부할 때 멈추는 지점을 찾아야 계획이 현실적입니다.",
            "{title} 학습은 성적표보다 실제 문제 풀이 과정에서 약점을 찾는 것이 좋습니다.",
            "{title} 학생은 시험 기간에 새 내용을 늘리기보다 반복 실수를 줄이는 데 집중해야 합니다.",
            "{title}에서는 과목별 목표를 다르게 잡아야 부담이 줄고 실행력이 생깁니다.",
            "{title}는 학년 특성에 맞춰 설명 속도와 과제량을 조절해야 합니다.",
            "{title} 학생은 공부 시작이 늦어지는 이유를 확인하고 작은 루틴부터 만들어야 합니다.",
            "{title}는 수행평가와 지필고사 일정을 함께 관리해야 시험 준비가 안정됩니다.",
            "{title}에서는 복습이 밀리지 않도록 수업 후 확인 기준을 간단히 정하는 것이 좋습니다.",
            "{title} 학습 목표는 점수뿐 아니라 공부 태도와 지속성을 함께 봐야 합니다.",
            "{title}는 다음 단계로 넘어가기 전 지금 학년에서 꼭 잡아야 할 내용을 정리해야 합니다.",
        ],
    }

    def __init__(
        self,
        template_dir=TEMPLATES_DIR,
        output_dir=OUTPUT_DIR,
        asset_dir=ASSETS_DIR,
        build_version=None,
        build_time=None,
    ):
        self.output_dir = Path(output_dir).resolve()
        self.asset_dir = Path(asset_dir).resolve()
        self.build_version = build_version
        self.build_time = build_time
        self._assets_copied = False
        self.environment = Environment(
            loader=FileSystemLoader(str(Path(template_dir).resolve())),
            autoescape=select_autoescape(["html"]),
        )

    def set_build_metadata(self, build_version, build_time):
        self.build_version = build_version
        self.build_time = build_time

    def render(self, page):
        if not getattr(page, "url", None):
            return

        self._copy_static_assets()
        template_name = "home.html" if page.page_type == PageType.NATION else "base.html"
        css_path = "/assets/css/home.css" if page.page_type == PageType.NATION else "/assets/css/site.css"
        template = self.environment.get_template(template_name)
        html = template.render(
            page=page,
            css_href=self._public_asset(css_path),
            content_html=self._enhance_content(page),
            home_subject_links=self._home_subject_links(page),
            home_subject_region_groups=self._home_subject_region_groups(page),
            summary_cards=self._summary_cards(page),
            faq_items=self._faq_items(page),
            link_groups=self._link_groups(page),
        )
        html = self._append_build_comment(html, template_name)
        output_path = self._output_path(page)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html, encoding="utf-8")

        for child in page.children:
            self.render(child)

    def _output_path(self, page):
        parts = [part for part in page.url.strip("/").split("/") if part]
        return self.output_dir.joinpath(*parts, "index.html")

    def _public_asset(self, public_path):
        if public_path.startswith("/"):
            return self._with_build_version(public_path)

        return self._with_build_version(f"/{public_path}")

    def _with_build_version(self, path):
        if not self.build_version:
            return path

        separator = "&" if "?" in path else "?"
        return f"{path}{separator}v={self.build_version}"

    def _summary_cards(self, page):
        if page.page_type == PageType.NATION:
            return []

        summaries = self.SUMMARY_BANK[self._content_group(page)]
        offset = self._stable_index(page, "summary-cards", len(summaries))
        selected = self._rotate(summaries, offset)[:4]
        return [{"title": title, "description": description} for title, description in selected]

    def _faq_items(self, page):
        return []

    def _home_subject_links(self, page):
        if page.page_type != PageType.NATION:
            return []

        return [
            {"title": title, "url": f"#{anchor}"}
            for title, anchor, _description in self.HOME_SUBJECT_SHORTCUTS
        ]

    def _home_subject_region_groups(self, page):
        if page.page_type != PageType.NATION:
            return []

        regions = [
            {
                "title": str(province.title).replace("과외", ""),
                "url": province.url,
            }
            for province in getattr(page, "children", [])
            if getattr(province, "url", None)
        ]
        if not regions:
            return []

        return [
            {
                "title": title,
                "anchor": anchor,
                "description": description,
                "regions": [
                    {
                        "title": f"{region['title']} {title} 지역 보기",
                        "url": region["url"],
                    }
                    for region in regions
                ],
            }
            for title, anchor, description in self.HOME_SUBJECT_SHORTCUTS
        ]

    def _link_groups(self, page):
        internal_links = getattr(page, "internal_links", {}) or {}
        groups = [
            ("상위 페이지", internal_links.get("parent")),
            ("하위 페이지", internal_links.get("children")),
            ("형제 페이지", internal_links.get("siblings")),
            ("관련 페이지", internal_links.get("related")),
            (getattr(page, "recommendation_title", "추천 학습 페이지"), internal_links.get("recommended")),
        ]

        link_groups = []
        seen = set()
        for title, value in groups:
            links = self._normalise_links(
                value,
                current_url=getattr(page, "url", None),
                seen=seen,
            )
            if not links:
                continue

            link_groups.append({"title": title, "visible": links[:12], "hidden": links[12:]})

        return link_groups

    def _normalise_links(self, value, current_url=None, seen=None):
        if not value:
            return []

        items = value if isinstance(value, list) else [value]
        links = []
        seen = seen if seen is not None else set()

        for item in items:
            if not item:
                continue

            url = item.get("url")
            title = item.get("title")
            if not url or not title or url == current_url or url in seen:
                continue

            seen.add(url)
            links.append({"title": title, "url": url})

        return links

    def _enhance_content(self, page):
        content = getattr(page, "content", "") or ""
        if page.page_type == PageType.NATION or not content:
            return content

        paragraphs = self._paragraph_count(content)
        component_count = self._component_count(paragraphs)
        enhanced_content = content

        if component_count:
            pattern = self._select_pattern(page)
            component_names = [pattern[index % len(pattern)] for index in range(component_count)]
            positions = self._insertion_positions(page, paragraphs, component_count)
            components = self._build_components(page, component_names)
            if positions and components:
                enhanced_content = self._insert_components(content, positions, components)

        return f"{enhanced_content}{self._ending_guidance_block(page, paragraphs)}"

    def _paragraph_count(self, content):
        return len(re.findall(r"</p>", content, flags=re.IGNORECASE))

    def _component_count(self, paragraph_count):
        if paragraph_count < 4:
            return 0
        if paragraph_count < 7:
            return 1
        if paragraph_count < 11:
            return 2
        if paragraph_count < 16:
            return 3
        if paragraph_count < 22:
            return 4
        return 5

    def _select_pattern(self, page):
        return self.READING_PATTERNS[self._stable_index(page, "pattern", len(self.READING_PATTERNS))]

    def _insertion_positions(self, page, paragraph_count, component_count):
        start_offset = self._stable_index(page, "position-start", 2)
        spread_offset = self._stable_index(page, "position-spread", 3)
        first = 2 + start_offset
        last = max(first, paragraph_count - 1)
        span = max(1, last - first)
        positions = []

        for index in range(component_count):
            if component_count == 1:
                position = min(last, first + spread_offset)
            else:
                position = first + round((span * index) / component_count)
                position += (spread_offset + index) % 2
                position = min(last, max(first, position))

            while position in positions and position < last:
                position += 1
            if position not in positions:
                positions.append(position)

        return sorted(positions)[:component_count]

    def _build_components(self, page, component_names):
        return [self._component_html(page, name, index) for index, name in enumerate(component_names)]

    def _component_html(self, page, component_name, index):
        if component_name == "tip":
            return self._tip_component(page, index)
        if component_name == "checklist":
            return self._checklist_component(page, index)
        if component_name == "summary":
            return self._summary_component(page, index)
        if component_name == "quote":
            return self._quote_component(page, index)
        if component_name == "faq":
            return self._faq_component(page, index)
        return ""

    def _insert_components(self, content, positions, components):
        position_map = dict(zip(positions, components))
        paragraph_index = 0

        def insert_after_paragraph(match):
            nonlocal paragraph_index

            paragraph_index += 1
            html = match.group(0)
            component = position_map.get(paragraph_index)
            if component:
                html += component
            return html

        return re.sub(r"</p>", insert_after_paragraph, content, flags=re.IGNORECASE)

    def _tip_component(self, page, index):
        title = self._page_title(page)
        tips = self.TIP_BANK[self._content_group(page)]
        tip = self._select_text(page, tips, f"tip-{index}").format(title=title)
        return (
            '<aside class="tip-box reading-insert" aria-label="학습 TIP">'
            '<strong class="box-title">TIP</strong>'
            f"<p>{escape(tip)}</p>"
            "</aside>"
        )

    def _checklist_component(self, page, index):
        title = self._page_title(page)
        items = self.CHECKLIST_BANK[self._content_group(page)]
        offset = self._stable_index(page, f"checklist-{index}", len(items))
        selected = self._rotate(items, offset)[:3]
        list_items = "".join(f"<li>{escape(item)}</li>" for item in selected)
        return (
            '<section class="checklist-box reading-insert" aria-label="확인 체크리스트">'
            '<strong class="box-title">체크리스트</strong>'
            "<ul>"
            f"{list_items}<li>{title} 상황에 맞춰 실천 가능 여부를 확인합니다.</li>"
            "</ul>"
            "</section>"
        )

    def _summary_component(self, page, index):
        title = self._page_title(page)
        summaries = self.SUMMARY_BANK[self._content_group(page)]
        summary_title, description = self._select_text(page, summaries, f"inline-summary-{index}")
        return (
            '<section class="summary-box reading-insert" aria-label="본문 요약">'
            f'<strong class="box-title">{escape(summary_title)}</strong>'
            f"<p>{title}에서는 {escape(description)}</p>"
            "</section>"
        )

    def _quote_component(self, page, index):
        title = self._page_title(page)
        quotes = [
            "좋은 수업은 조건을 나열하는 데서 끝나지 않고 학생이 다음 공부를 이어가게 만드는 과정입니다.",
            "꾸준한 성과는 큰 계획보다 매주 확인 가능한 작은 변화에서 시작됩니다.",
            "학생에게 맞는 설명은 어려운 내용을 쉽게 만드는 것뿐 아니라 다시 해볼 용기를 남깁니다.",
            "공부 흐름이 안정되면 시험 준비도 급한 암기가 아니라 확인 가능한 과정이 됩니다.",
            "맞춤 학습의 핵심은 더 많이 시키는 것이 아니라 지금 필요한 순서를 정확히 잡는 것입니다.",
        ]
        quote = self._select_text(page, quotes, f"quote-{index}")
        return (
            '<blockquote class="reading-quote reading-insert">'
            f"<p>{title} 선택에서는 {escape(quote)}</p>"
            "</blockquote>"
        )

    def _faq_component(self, page, index):
        title = self._page_title(page)
        faqs = self.FAQ_BANK[self._content_group(page)]
        question, answer = self._select_text(page, faqs, f"faq-{index}")
        return (
            '<section class="inline-faq reading-insert" aria-label="자주 묻는 질문">'
            '<details class="faq-item">'
            f"<summary>{escape(question.format(title=title))}</summary>"
            f"<p>{escape(answer.format(title=title))}</p>"
            "</details>"
            "</section>"
        )

    def _ending_guidance_block(self, page, paragraph_count):
        if paragraph_count < 2 or page.page_type not in self.PAGE_TYPE_GUIDANCE:
            return ""

        title = self._page_title(page)
        sentences = self._page_type_sentences(page)
        card_groups = self._guidance_card_groups(page)
        sentence_html = "".join(f"<p>{escape(sentence.format(title=title))}</p>" for sentence in sentences)
        card_group_html = self._guidance_card_group_list(card_groups)
        return (
            '<section class="summary-box reading-insert" aria-label="페이지 안내">'
            '<strong class="box-title">페이지 안내</strong>'
            f"{sentence_html}"
            f"{card_group_html}"
            "</section>"
        )

    def _page_type_sentences(self, page):
        sentence_pool = self.PAGE_TYPE_GUIDANCE.get(page.page_type, [])
        if not sentence_pool:
            return []

        offset = self._stable_index(page, "page-type-guidance", len(sentence_pool))
        rotated = self._rotate(sentence_pool, offset)
        selected = []
        seen_starts = set()

        for sentence in rotated:
            marker = sentence.split(" ", 2)[1] if " " in sentence else sentence[:8]
            if marker in seen_starts:
                continue

            seen_starts.add(marker)
            selected.append(sentence)
            if len(selected) == 3:
                break

        return selected or rotated[:3]

    def _guidance_card_groups(self, page):
        children = self._all_child_links(page)
        subject_links = self._get_subject_links(page)
        if not children and not subject_links:
            return []

        page_title = str(getattr(page, "title", ""))
        base_title = self._region_title_base(page_title)
        child_label = self._child_link_label(page)
        featured = self._get_featured_links(children, limit=6)
        featured_urls = {link.get("url") for link in featured}
        remaining_children = [
            link for link in children if link.get("url") not in featured_urls
        ]
        groups = []

        if subject_links:
            groups.append(
                {
                    "title": "과목 선택",
                    "links": subject_links,
                }
            )

        if featured:
            groups.append(
                {
                    "title": f"{base_title} 인기 {child_label}",
                    "links": featured,
                }
            )

        if remaining_children:
            groups.append(
                {
                    "title": f"전체 {base_title} {child_label}",
                    "links": remaining_children,
                }
            )
        return groups

    def _get_subject_links(self, page):
        if page.page_type not in {PageType.PROVINCE, PageType.CITY, PageType.DISTRICT, PageType.DONG}:
            return []

        subject_names = [title for title, _anchor, _description in self.HOME_SUBJECT_SHORTCUTS]
        direct_subjects = [
            child
            for child in getattr(page, "children", [])
            if child.page_type == PageType.SUBJECT and getattr(child, "url", None)
        ]
        links = []
        seen_urls = set()

        for subject_name in subject_names:
            target = next(
                (
                    item
                    for item in direct_subjects
                    if str(item.title).endswith(subject_name)
                    and getattr(item, "url", None)
                    and item.url not in seen_urls
                ),
                None,
            )
            if not target:
                continue

            seen_urls.add(target.url)
            links.append({"title": subject_name, "url": target.url})

        return links

    def _get_featured_links(self, links, limit=6):
        return links[:limit]

    def _all_child_links(self, page):
        internal_links = getattr(page, "internal_links", {}) or {}
        links = internal_links.get("children") or []
        if not isinstance(links, list):
            links = [links]
        subject_urls = {
            child.url
            for child in getattr(page, "children", [])
            if child.page_type == PageType.SUBJECT and getattr(child, "url", None)
        }
        region_links = [link for link in links if link.get("url") not in subject_urls]
        return self._unique_link_dicts(region_links)

    def _child_link_label(self, page):
        children = getattr(page, "children", []) or []
        child_type = getattr(children[0], "page_type", None) if children else None
        labels = {
            PageType.PROVINCE: "지역",
            PageType.CITY: "지역",
            PageType.DISTRICT: "지역",
            PageType.DONG: "지역",
            PageType.SUBJECT: "과목",
            PageType.GRADE: "학년",
            PageType.SCHOOL: "학교",
        }
        return labels.get(child_type, "지역")

    def _region_title_base(self, title):
        return title[:-2] if title.endswith("과외") else title

    def _guidance_card_group_list(self, groups):
        if not groups:
            return ""

        return "".join(
            f'<h3>{escape(group["title"])}</h3>'
            f'{self._card_link_grid(group["links"])}'
            for group in groups
        )

    def _card_link_grid(self, links):
        items = "".join(
            '<li>'
            f'<a class="card link-card" href="{escape(link["url"])}">'
            f'<span>{escape(link["title"])}</span>'
            "</a>"
            "</li>"
            for link in links
        )
        return f'<ul class="card-grid">{items}</ul>'

    def _guidance_links(self, page):
        links = []
        internal_links = getattr(page, "internal_links", {}) or {}

        for key in ("recommended", "related", "children", "siblings"):
            value = internal_links.get(key)
            if not value:
                continue

            items = value if isinstance(value, list) else [value]
            for item in items:
                if not item or item.get("url") == getattr(page, "url", None):
                    continue

                links.append(item)

        return self._unique_link_dicts(links)[:5]

    def _guidance_link_list(self, links):
        if not links:
            return "<p>현재 페이지의 상위·하위 정보를 함께 보면 학습 방향을 더 쉽게 잡을 수 있습니다.</p>"

        items = "".join(
            f'<li><a href="{escape(link["url"])}">{escape(link["title"])}</a></li>'
            for link in links
        )
        return f"<ul>{items}</ul>"

    def _unique_link_dicts(self, links):
        unique_links = []
        seen = set()

        for link in links:
            url = link.get("url")
            if not url or url in seen:
                continue

            seen.add(url)
            unique_links.append(link)

        return unique_links

    def _content_group(self, page):
        return self.TYPE_GROUPS.get(page.page_type, "default")

    def _page_title(self, page):
        return escape(str(page.title))

    def _select_text(self, page, items, salt):
        return items[self._stable_index(page, salt, len(items))]

    def _stable_index(self, page, salt, length):
        key = f"{getattr(page, 'url', '')}|{getattr(page, 'title', '')}|{page.page_type.value}|{salt}"
        digest = sha256(key.encode("utf-8")).hexdigest()
        return int(digest[:12], 16) % length

    def _rotate(self, items, offset):
        if not items:
            return []
        return items[offset:] + items[:offset]

    def _flatten_pages(self, page):
        pages = []
        self._walk_page(page, pages)
        return pages

    def _walk_page(self, page, pages):
        pages.append(page)
        for child in getattr(page, "children", []):
            self._walk_page(child, pages)

    def _append_build_comment(self, html, template_name):
        if not self.build_version or not self.build_time:
            return html

        comment = "\n".join(
            [
                "<!--",
                f"Build Time: {self.build_time}",
                f"Build Version: {self.build_version}",
                f"Template: {template_name}",
                "-->",
            ]
        )
        return f"{html.rstrip()}\n{comment}\n"

    def _copy_static_assets(self):
        if self._assets_copied:
            return

        for css_name in ["site.css", "home.css"]:
            css_source = self.asset_dir / "css" / css_name
            if not css_source.exists():
                continue

            css_output = self.output_dir / "assets" / "css" / css_name
            css_output.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(css_source, css_output)

        self._assets_copied = True

