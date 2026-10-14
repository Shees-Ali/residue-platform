import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import tableware from '@/assets/tableware.jpg';
import briquettes from '@/assets/briquettes.jpg';
import compost from '@/assets/compost.jpg';
import boards from '@/assets/boards.jpg';
import notebooks from '@/assets/notebooks.jpg';
import planters from '@/assets/planters.jpg';
export type Status = 'Pending' | 'Accepted' | 'In transit' | 'Delivered' | 'Received' | 'Rejected';
export interface Collection { id: string; name: string; phone: string; crop: string; quantity: number; district: string; village: string; date: string; notes: string; status: Status; }
export interface Product { id: string; name: string; category: string; price: number; description: string; image: string; unit: string; listed: boolean; }
export const seedRequests: Collection[] = [
{id:'FL-1024',name:'Ahmed Raza',phone:'0300 1234567',crop:'Wheat straw',quantity:3.5,district:'Gujranwala',village:'Kamoke',date:'2026-10-15',notes:'Straw is baled and ready for pickup.',status:'Accepted'},
{id:'FL-1023',name:'Muhammad Aslam',phone:'0301 2345678',crop:'Rice straw',quantity:1.5,district:'Sheikhupura',village:'Muridke',date:'2026-10-10',notes:'',status:'Received'},
{id:'FL-1022',name:'Muhammad Aslam',phone:'0301 2345678',crop:'Wheat straw',quantity:2.8,district:'Sheikhupura',village:'Muridke',date:'2026-10-05',notes:'',status:'Received'},
{id:'FL-1021',name:'Bilal Hussain',phone:'0321 3456789',crop:'Sugarcane bagasse',quantity:4,district:'Faisalabad',village:'Jaranwala',date:'2026-10-16',notes:'Access available for a medium truck.',status:'Pending'},
];
export const seedProducts: Product[] = [
{id:'p1',name:'Rice Straw Tableware',category:'Home & Living',price:850,description:'A set of 6 beautifully simple, compostable plates made from Punjab rice straw. A lighter footprint at every meal.',image:tableware,unit:'Set of 6',listed:true},
{id:'p2',name:'Biomass Fuel Briquettes',category:'Clean Energy',price:1200,description:'High-density fuel briquettes from agricultural residue. A practical alternative for efficient, cleaner heating.',image:briquettes,unit:'10 kg bag',listed:true},
{id:'p3',name:'Organic Soil Compost',category:'Farming & Garden',price:650,description:'Nutrient-rich compost made from repurposed crop residue, returning goodness to the soil.',image:compost,unit:'5 kg bag',listed:true},
{id:'p4',name:'Straw Fiber Boards',category:'Building Materials',price:2400,description:'Durable fiber panels made with wheat straw for sustainable interiors and everyday building projects.',image:boards,unit:'Per board',listed:true},
{id:'p5',name:'Harvest Paper Notebooks',category:'Home & Living',price:450,description:'Two handmade notebooks with textured residue-based paper. Fresh ideas, without fresh-cut trees.',image:notebooks,unit:'Pack of 2',listed:true},
{id:'p6',name:'Plantable Seedling Pots',category:'Farming & Garden',price:380,description:'Biodegradable fiber pots that go straight into the earth. Grow a little greener with a set of three.',image:planters,unit:'Set of 3',listed:true},
];
interface DemoState { requests: Collection[]; products: Product[]; cart: Record<string,number>; activity: string[]; }
const initial: DemoState = {requests:seedRequests,products:seedProducts,cart:{},activity:['Ahmed Raza’s collection was accepted by GreenCycle Industries.','1.5 tonnes of rice straw received from Muridke.','Bilal Hussain submitted a collection request.']};
interface DemoContextValue extends DemoState { submit: (input: Omit<Collection,'id'|'status'>)=>void; advance:(id:string,status:Status)=>void; addProduct:(input:Omit<Product,'id'|'image'|'listed'>)=>void; toggleProduct:(id:string)=>void; changeCart:(id:string,delta:number)=>void; reset:()=>void; ready:boolean; }
const DemoContext=createContext<DemoContextValue | null>(null);
export function DemoProvider({children}:{children:ReactNode}) {
 const [state,setState]=useState<DemoState>(initial); const [ready,setReady]=useState(false);
 useEffect(()=>{try {const stored=localStorage.getItem('residue-demo-v1');if(stored){const parsed=JSON.parse(stored);if(Array.isArray(parsed.requests)&&Array.isArray(parsed.products)&&parsed.cart&&Array.isArray(parsed.activity))setState(parsed);}}catch{}setReady(true);},[]);
 useEffect(()=>{if(ready){try{localStorage.setItem('residue-demo-v1',JSON.stringify(state));}catch{}}},[state,ready]);
 const submit=(input:Omit<Collection,'id'|'status'>)=>setState(s=>({...s,requests:[{...input,id:`FL-${1025+s.requests.length-seedRequests.length}`,status:'Pending'},...s.requests],activity:[`${input.name} submitted ${input.quantity} tonnes of ${input.crop.toLowerCase()} in ${input.district}.`,...s.activity].slice(0,12)}));
 const advance=(id:string,status:Status)=>setState(s=>{const r=s.requests.find(r=>r.id===id);if(!r)return s; const valid:Record<Status,Status[]>= {Pending:['Accepted','Rejected'],Accepted:['In transit'],'In transit':['Delivered'],Delivered:['Received'],Received:[],Rejected:[]};if(!valid[r.status].includes(status))return s;return {...s,requests:s.requests.map(r=>r.id===id?{...r,status}:r),activity:[`${id} · ${r.quantity} tonnes of ${r.crop.toLowerCase()} — ${status.toLowerCase()}.`,...s.activity].slice(0,12)};});
 return <DemoContext.Provider value={{...state,ready,submit,advance,addProduct:input=>setState(s=>({...s,products:[...s.products,{...input,id:`p${s.products.length+1}`,image:compost,listed:true}]})),toggleProduct:id=>setState(s=>({...s,products:s.products.map(p=>p.id===id?{...p,listed:!p.listed}:p)})),changeCart:(id,delta)=>setState(s=>({...s,cart:{...s.cart,[id]:Math.max(0,(s.cart[id]||0)+delta)}})),reset:()=>setState(initial)}}>{children}</DemoContext.Provider>;
}
export function useDemo(){const value=useContext(DemoContext);if(!value)throw new Error('DemoProvider required');return value;}
export const currency=(price:number)=>`PKR ${price.toLocaleString('en-PK')}`;
export const formatDate=(date:string)=>new Date(`${date}T12:00:00`).toLocaleDateString('en-GB',{day:'numeric',month:'short',year:'numeric'});
