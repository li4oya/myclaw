# Table 4: Taxonomy of Evaluation Benchmarks for Self-Evolving Agents Systems

**Total Benchmarks: 49**

| Seq | Benchmark | Ref | Domain | Modality | Task Format | Key Features |
|-----|-----------|-----|--------|----------|-------------|---------------|
| 1 | MMLU-Pro | [295] | GeneralKnowledge | Text | MCQ(10-options) | RobustReasoning,LowNoise |
| 2 | HotpotQA | [296] | GeneralKnowledge | Text | ExtractiveQA | Multi-hop,SupportingFacts |
| 3 | MMLU | [297] | GeneralKnowledge | Text | MCQ(4-options) | 57Disciplines,BroadCoverage |
| 4 | MuSiQue | [298] | GeneralKnowledge | Text | ExtractiveQA | ConnectedMulti-hop,Harder § |
| 5 | NQ | [299] | GeneralKnowledge | Text | Short/LongQA | RealUserQueries,Open-Domain § |
| 6 | TriviaQA | [300] | GeneralKnowledge | Text | QA | ReadingComp.,EvidenceTriples |
| 7 | PopQA | [301] | GeneralKnowledge | Text | ShortQA | Long-TailEntities,RAGFocus |
| 8 | 2WikiMultiHopQA | [302] | GeneralKnowledge | Text | QA | StructuredReasoningPaths |
| 9 | BBH | [303] | GeneralKnowledge | Text | Mixed(QA/MCQ) | HardBIG-BenchSubset,CoT § |
| 10 | AGIEval | [304] | GeneralKnowledge | Text | MCQ | Human-CentricExams(SAT/LSAT) § |
| 11 | ARC | [305] | GeneralKnowledge | Visual | GridGeneration | Abstraction,Few-Shot,CoreKnowledge § |
| 12 | ARC-AGI | [306] | AbstractReasoning | Visual | GridTransformation | FluidIntelligence,Human-easyAI-hard § |
| 13 | NarrativeQA | [307] | GeneralKnowledge | Text | GenerativeQA | VeryLongContext(Books/Scripts) § |
| 14 | LongBench | [308] | GeneralKnowledge | Text | Mixed | LongContext,Multi-TaskEval § |
| 15 | HLE | [309] | GeneralKnowledge | Multimodal | Mixed(MCQ/QA) | FrontierKnowledge,Un-googleable |
| 16 | GPQA | [310] | ScientificReasoning | Text | MCQ | PhD-Level,Google-Proof § |
| 17 | SuperGPQA | [311] | ScientificReasoning | Text | MCQ | 285Disciplines,LightIndustry/Agri |
| 18 | SciBench | [312] | ScientificReasoning | Text | QA | College-Level,Step-by-StepCalc § |
| 19 | ChemBench | [313] | ScientificReasoning | Text | Mixed | Chemistry,AutonomousLabs § |
| 20 | SciQA | [314] | ScientificReasoning | Text | QA | KnowledgeGraph,ScientificData |
| 21 | AIME | [315] | MathematicalReasoning | Text | NumericQA | MathCompetition,HardDifficulty |
| 22 | OlympiadBench | [316] | MathematicalReasoning | Multimodal | Mixed(QA/MCQ) | VisualReasoning,Olympiad-Level § |
| 23 | GSM8K | [317] | MathematicalReasoning | Text | NumericQA | GradeSchoolMath,CoTFocus |
| 24 | MATH | [318] | MathematicalReasoning | Text | Latex/QA | ChallengingMath,DiverseTopics |
| 25 | AMC | [319] | MathematicalReasoning | Text | MCQ | Pre-Olympiad,CompetitionMath |
| 26 | LiveCodeBench | [320] | CodeGeneration | Text | FunctionGen | Contamination-Free,LiveData § |
| 27 | BigCodeBench | [321] | CodeGeneration | Text | Function/FullGen | ComplexLibraries,InstructionFollowing § |
| 28 | HumanEval | [322] | CodeGeneration | Text | FunctionGen | FunctionalCorrectness,Docstrings § |
| 29 | MBPP | [323] | CodeGeneration | Text | FunctionGen | BasicProgramming,Semantic § |
| 30 | EvalPlus | [324] | CodeGeneration | Text | FunctionGen | RigorousEval,80xTestCases § |
| 31 | MultiPL-E | [325] | CodeGeneration | Text | FunctionGen(Polyglot) | 18+Languages,ParallelCorpus § |
| 32 | CRUXEval | [326] | CodeGeneration | Text | Input/OutputPrediction | ExecutionSimulation,CoTFocus § |
| 33 | WebArena | [327] | WebNavigation | Text/HTML | Env.Interaction | RealisticTasks,Long-Horizon § |
| 34 | WebShop | [328] | WebNavigation | Text | Env.Interaction | E-commerce,DecisionMaking § |
| 35 | MT-Mind2Web | [329] | WebNavigation | Text | ActionSeq. | Multi-Turn,Generalization |
| 36 | Mind2Web | [330] | WebNavigation | Text | ActionSeq. | GeneralistAgent,RealDOM § |
| 37 | WebVoyager | [104] | WebNavigation | Multimodal | Env.Interaction | End-to-End,VisualNavigation § |
| 38 | VisualWebArena | [331] | WebNavigation | Multimodal | Env.Interaction | Visual/HTML,HybridInteraction § |
| 39 | ToolLLM | [332] | ToolUsage | Text | APICalls | Large-ScaleAPIs,InstructionTuning § |
| 40 | AgentGym | [198] | UnifiedFrameworks | Multimodal | Env.Interaction | InteractiveLearning,Diversity § |
| 41 | AgentBoard | [333] | UnifiedFrameworks | Multimodal | Env.Interaction | AnalyticDashboard,UnifiedEval § |
| 42 | ReasoningGym | [196] | UnifiedFrameworks | Text | Interaction | Algorithmic,DynamicTasks § |
| 43 | ALFWorld | [334] | UnifiedFrameworks | Text | TextInteraction | Text-World,HouseholdTasks § |
| 44 | AgentBench | [335] | UnifiedFrameworks | Text | Mixed | Comprehensive,Multi-Environment § |
| 45 | GAIA | [336] | UnifiedFrameworks | Multimodal | QAw/Tools | GeneralAssistant,HardReasoning |
| 46 | DeepResearchBench | [108] | UnifiedFrameworks | Text | WebSearch | Long-formResearch,CitationEval § |
| 47 | SWE-bench | [337] | SoftwareEngineering | Text | PatchGen | RealGitHubIssues,Repo-Level § |
| 48 | Terminal-Bench | [338] | OSOperations | Text | CLIInteraction | LinuxCommandLine,Security § |
| 49 | OSWorld | [339] | OSOperations | Multimodal | GUI/Desktop | Cross-App,FullOSControl § |
