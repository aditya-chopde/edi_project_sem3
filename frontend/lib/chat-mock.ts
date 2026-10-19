import type { ChatSource, ResponseLanguage } from "@/lib/chat-types";

export const demoSources: ChatSource[] = [
  {
    id: "source-education-sanskrit",
    documentId: "demo-treatise-education",
    title: "A Treatise on the Aim of Education",
    languageScript: "Sanskrit · Devanagari",
    pageSection: "Illustrative record · Folio 12r",
    snippet: "विद्या नाम नरस्य रूपमधिकं प्रच्छन्नगुप्तं धनम् ।",
    relevanceScore: 0.94,
    isIllustrative: true,
  },
  {
    id: "source-education-marathi",
    documentId: "demo-poona-daftar",
    title: "The Poona Daftar · Education Records",
    languageScript: "Old Marathi · Modi",
    pageSection: "Illustrative record · Page 07",
    snippet: "शास्त्राध्ययन व लेखन यांचा अभ्यास गुरुकुलामध्ये चालत असे...",
    relevanceScore: 0.88,
    isIllustrative: true,
  },
  {
    id: "source-education-persian",
    documentId: "demo-deccan-chronicle",
    title: "Persian Chronicle of the Deccan",
    languageScript: "Persian · Nastaliq",
    pageSection: "Illustrative record · Folio 32",
    snippet: "در مکتب خانه، علوم و آداب به شاگردان آموخته می شد.",
    relevanceScore: 0.81,
    isIllustrative: true,
  },
];

const answerByLanguage: Record<ResponseLanguage, string> = {
  English:
    "This is a **front-end demonstration**, not a verified historical finding. No live archive is connected, so the illustrative records below cannot substantiate a claim about your question.\n\n### How to read this demo\n- The response language is independent of the source languages shown below.\n- Select a citation such as [source:source-education-sanskrit] to inspect its matching example record.\n- The records are interface fixtures only; verify any historical claim against an authoritative edition or archive.",
  Hindi:
    "यह **फ्रंट-एंड प्रदर्शन** है, सत्यापित ऐतिहासिक निष्कर्ष नहीं। कोई वास्तविक अभिलेखागार जुड़ा नहीं है, इसलिए नीचे दिए उदाहरण आपके प्रश्न के प्रमाण नहीं हैं।\n\n### इस प्रदर्शन को कैसे पढ़ें\n- उत्तर की भाषा नीचे दिखाए गए स्रोतों की भाषाओं से स्वतंत्र है।\n- संबंधित उदाहरण देखने के लिए [source:source-education-sanskrit] जैसे संदर्भ चुनें।\n- ये केवल इंटरफ़ेस के उदाहरण हैं; ऐतिहासिक दावों की पुष्टि विश्वसनीय संस्करण या अभिलेखागार से करें।",
  Marathi:
    "हे **फ्रंट-एंड प्रात्यक्षिक** आहे; पडताळलेला ऐतिहासिक निष्कर्ष नाही. थेट संग्रह जोडलेला नसल्यामुळे खालील उदाहरण नोंदी तुमच्या प्रश्नाचा पुरावा ठरत नाहीत.\n\n### हे प्रात्यक्षिक कसे वाचावे\n- उत्तराची भाषा खाली दाखवलेल्या स्रोतांच्या भाषांपासून स्वतंत्र आहे.\n- संबंधित उदाहरण पाहण्यासाठी [source:source-education-marathi] सारखा संदर्भ निवडा.\n- या केवळ इंटरफेसमधील नमुना नोंदी आहेत; ऐतिहासिक दाव्यांची अधिकृत आवृत्ती किंवा संग्रहातून खात्री करा.",
  Hinglish:
    "Yeh **front-end demo** hai, verified historical finding nahi. Koi live archive connected nahi hai, isliye neeche diye gaye illustrative records aapke question ka evidence nahi hain.\n\n### Is demo ko kaise padhein\n- Response language neeche dikhayi gayi source languages se independent hai.\n- Matching example dekhne ke liye [source:source-education-sanskrit] jaise citation par click karein.\n- Yeh sirf interface fixtures hain; historical claims ko authoritative edition ya archive se verify karein.",
  Sanskrit:
    "इदं **अग्रभागस्य प्रदर्शनम्** अस्ति, न तु प्रमाणितम् ऐतिहासिकं निष्कर्षम्। सजीवः अभिलेखागारः न संयोजितः; अतः अधोलिखितानि उदाहरणानि प्रश्नस्य प्रमाणानि न सन्ति।\n\n### प्रदर्शनस्य पठनम्\n- उत्तरस्य भाषा अधः प्रदर्शितभाषाभ्यः स्वतन्त्रा अस्ति।\n- सम्बद्धम् उदाहरणं द्रष्टुं [source:source-education-sanskrit] इत्येतत् चिनोतु।\n- एतानि केवलं प्रदर्शनस्य उदाहरणानि; ऐतिहासिकदावान् प्रामाणिकग्रन्थेन अभिलेखागारेण वा परीक्षेत।",
};

export function createDemoAnswer(language: ResponseLanguage): string {
  return answerByLanguage[language];
}
