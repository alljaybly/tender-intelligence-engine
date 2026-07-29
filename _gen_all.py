import os  
from pathlib import Path  
BASE = Path("tender-engine-frontend/src/components/landing")  
BASE.mkdir(parents=True, exist_ok=True)  
  
def w(name, content):  
    p = BASE / name  
    p.write_text(content, encoding="utf-8", newline="\n")  
    print(f"Created {name}")  
  
w("HowItWorks.tsx", """ >> _gen_all.py && echo export default function HowItWorks() { >> _gen_all.py && echo   const steps = [ >> _gen_all.py && echo     {number:"1",title:"Upload Tender",desc:"Upload your tender document.",icon:"??"}, >> _gen_all.py && echo     {number:"2",title:"AI Extracts Structure",desc:"Pipeline extracts sector, BOQ, workforce.",icon:"??"}, >> _gen_all.py && echo     {number:"3",title:"Generate Reports",desc:"Get pricing, reports, and exports.",icon:"??"}, >> _gen_all.py && echo   ]; >> _gen_all.py && echo   return(<section className="py-20 bg-white"><div className="max-w-7xl mx-auto px-4"><h2 className="text-3xl font-bold text-center">How It Works</h2><div className="grid md:grid-cols-3 gap-8 mt-12">{steps.map(s=>(<div key={s.number} className="text-center"><div className="text-3xl mb-4">{s.icon}</div><h3 className="text-lg font-semibold mb-2">{s.title}</h3><p className="text-sm text-gray-600">{s.desc}</p></div>))}</div></div></section>);} >> _gen_all.py && echo """  
  
w("CTASection.tsx", """ >> _gen_all.py && echo export default function CTASection() { >> _gen_all.py && echo   return( >> _gen_all.py && echo     <section className="py-20 bg-gray-900"> >> _gen_all.py && echo       <div className="max-w-4xl mx-auto px-4 text-center"> >> _gen_all.py && echo         <h2 className="text-3xl font-bold text-white">Start Processing Tenders Smarter</h2> >> _gen_all.py && echo         <p className="mt-4 text-gray-400">Reduce processing time from hours to minutes.</p> >> _gen_all.py && echo         <div className="mt-10 flex gap-4 justify-center"> >> _gen_all.py && echo           <a href="/register" className="px-8 py-3 bg-white text-gray-900 rounded-lg font-medium">Create Free Account</a> >> _gen_all.py && echo           <a href="/demo" className="px-8 py-3 border border-gray-600 text-white rounded-lg font-medium">Try Demo</a> >> _gen_all.py && echo         </div> >> _gen_all.py && echo       </div> >> _gen_all.py && echo     </section> >> _gen_all.py && echo   ); >> _gen_all.py && echo } >> _gen_all.py && echo """  
