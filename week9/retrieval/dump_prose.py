import sys,json
from pathlib import Path
from dotenv import load_dotenv

HERE=Path(__file__).resolve()
load_dotenv(HERE.parent.parent.parent/".env")
load_dotenv()
sys.path.insert(0,str(HERE.parent))
from prose_retriever import retrieve
from prose_generate import generate,_build_context
from judge_prose import judge

EVAL=HERE.parent.parent.parent/"week8"/"eval"/"prose_eval.json"
OUT_MD=HERE.parent/"prose_answers_review.md"
OUT_JSON=HERE.parent/"prose_answers_review.json"

def main():
    data=json.load(open(EVAL))
    limit=int(sys.argv[1]) if len(sys.argv)>1 else len(data)
    data=data[:limit]
    
    records=[]
    for i,it in enumerate(data,1):
        q,tk,ref=it["question"],it["ticker"],it.get("reference_answer","")
        rec={"id":it["id"],"ticker":tk,"question":q,"reference":ref}
        try:
            out=retrieve(q,tickers=tk,top_k=10)
            g=generate(q,out["parents"])
            rec["answer"]=g["answer"]
            rec["declined"]=g["declined"]
            if not g["declined"]:
                ptext=_build_context(out["parents"])
                f,c=judge(q,g["answer"],ptext,ref)
                rec["faithfulness"]=f
                rec["correctness"]=c
            else:
                rec["faithfulness"]=rec["correctness"]=None
        except Exception as exc:
            rec["answer"]=f"ERROR: {exc}"
            rec["declined"]=None
            rec["faithfulness"]=rec["correctness"]=None
        records.append(rec)
        if i%10==0:
            print(f" ...{i}/{len(data)}")
    def keysort(r):
        f=r.get("faithfulness") or 0
        c=r.get("correctness") or 0
        return f+c
    records.sort(key=keysort)

    with open(OUT_MD,"w") as fh:
        fh.write("# Prose answers - manual review (worst-scored first)\n\n")
        for r in records:
            fh.write(f"## {r['id']}  (faith={r.get('faithfulness')} "
                     f"corr={r.get('correctness')} declined={r.get('declined')})\n\n")
            fh.write(f"**Q:** {r['question']}\n\n")
            fh.write(f"**Reference:** {r['reference']}\n\n")
            fh.write(f"**Generated:** {r['answer']}\n\n")
            fh.write("---\n\n")
    json.dump(records, open(OUT_JSON, "w"), indent=2)
    print(f"\nwrote {OUT_MD}")
    print(f"wrote {OUT_JSON}")
    print(f"{len(records)} answers. Review worst-first; check judge scores match your read.")
 
 
if __name__ == "__main__":
    main()