import { useEffect, useMemo, useState, type FormEvent } from 'react';
import {
  ArrowRight, Plus, Leaf, Package, Truck, CheckCircle2, Wheat, MapPin, CalendarDays,
  Factory as FactoryIcon, ShoppingBag, Users, Sprout, X, Check, RotateCcw, ShieldCheck,
  Camera, Scale, Banknote, Megaphone, Gavel,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogTitle, DialogDescription } from '@/components/ui/dialog';
import {
  PageHeading, Stat, SectionTitle, JobTracker, GradeCard, LedgerPanel, SplitBreakdown,
  KV, Pill, pkr, JOB_STATE_LABEL, DemoLabel,
} from './common';
import { useDomain } from './domain-state';
import { escrowFor, PLATFORM_FEE_BPS, TRANSPORT_RATE_PER_TONNE } from '@/lib/domain/engine';
import { DEFAULT_SHARES } from '@/lib/domain/revenueShare';
import { rankFactories } from '@/lib/domain/assignment';
import { seedDomain } from '@/lib/domain/seed';
import type { Grade, Job, ResidueType } from '@/lib/domain/types';
import field from '@/assets/punjab-field.jpg';

function Field({label,children}:{label:string;children:React.ReactNode}){return <label className="form-field"><span>{label}</span>{children}</label>;}
const RESIDUE_LABEL: Record<ResidueType,string> = { rice_straw:'Rice straw', wheat_straw:'Wheat straw', cotton_stalk:'Cotton stalk', sugarcane_trash:'Sugarcane trash' };
const RESIDUE_KEYS = Object.keys(RESIDUE_LABEL) as ResidueType[];

/* ================================================================== *
 * F1 · F2 · F3 · F4 — Farmer Portal
 * ================================================================== */
export function FarmerPortal(){
  const { state, dispatch, ready } = useDomain();
  const me = state.farmers[0]; // demo is signed in as the first farmer
  const [open,setOpen]=useState(false);
  const mine = useMemo(()=>{
    const lotIds = new Set(state.lots.filter(l=>l.farmerId===me.id).map(l=>l.id));
    return state.jobs.filter(j=>lotIds.has(j.lotId));
  },[state.jobs,state.lots,me.id]);
  const collected = mine.reduce((n,j)=>n+(j.finalWeightTonnes??0),0);
  const active = mine.filter(j=>!['settled','rejected','disputed'].includes(j.state));
  // F4: a job the factory confirmed is waiting on the farmer's yes/dispute.
  const toVerify = mine.filter(j=>j.state==='confirmed');

  function onSubmit(e:FormEvent<HTMLFormElement>){
    e.preventDefault();
    const d = new FormData(e.currentTarget);
    // F1: the same fields the voice agent collects by call.
    dispatch({ type:'submitLot', farmerId:me.id, residueType:String(d.get('residue')) as ResidueType,
      quantityTonnes:Number(d.get('quantity')), village:String(d.get('village')), district:String(d.get('district')),
      pickupWindow:String(d.get('date')), nowMs:Date.now() });
    setOpen(false);
  }

  return <><PageHeading eyebrow="FARMER PORTAL" title="Assalam-o-Alaikum, Aslam!" description="Your harvest has more to give. Let’s turn residue into opportunity." action={<Button onClick={()=>setOpen(true)} disabled={!ready} className="h-11"><Plus/>Report residue</Button>}/>
  <div className="farmer-banner"><img src={field} width={1600} height={800} alt="Golden rice straw gathered in a Punjab field"/><div className="banner-shade"/><div className="banner-copy"><span className="banner-eyebrow"><Sprout size={15}/>A NEW LIFE FOR EVERY HARVEST</span><h2>Don’t burn it.<br/>Put it back in the loop.</h2><p>Better soil. Cleaner air. A stronger Punjab.</p><Button variant="secondary" onClick={()=>setOpen(true)}>Schedule a collection <ArrowRight/></Button></div><span className="banner-location"><MapPin size={13}/>Punjab, Pakistan</span></div>
  <div className="stats-grid three">
    <Stat label="My lots" value={mine.length} icon={Wheat} note="Reported by call or form"/>
    <Stat label="Residue delivered" value={`${collected.toFixed(1)} t`} icon={Leaf} note="Kept out of open-field burning" tone="gold"/>
    <Stat label="Active jobs" value={active.length} icon={Truck} note="Moving toward settlement"/>
  </div>

  {toVerify.length>0 && <SectionTitle title="Confirm your weight and payment (F4)"/>}
  <div className="jobs-grid">
    {toVerify.map(j=>{
      const lot=state.lots.find(l=>l.id===j.lotId)!;
      const factory=state.factories.find(f=>f.id===j.factoryId);
      const escrow = factory ? escrowFor(j,lot,factory) : 0;
      const fee = Math.round(escrow*PLATFORM_FEE_BPS/10000);
      const myShare = Math.round(((escrow-fee)*DEFAULT_SHARES.farmer)/10000);
      return <article className="job-card" key={j.id}>
        <div className="flex justify-between gap-2"><span className="text-xs font-medium text-muted-foreground">{j.id} · {factory?.name??'Unassigned'}</span><Pill tone="gold">Awaiting you</Pill></div>
        <h3 className="mt-4">{lot.quantityTonnes} t {RESIDUE_LABEL[lot.residueType]}</h3>
        <div className="job-details"><p><MapPin/>{lot.village}, {lot.district}</p><p><Scale/>{j.finalWeightTonnes} t weighed</p></div>
        <dl style={{margin:'8px 0'}}>
          <KV k="Escrow funded" v={pkr(escrow)}/>
          <KV k="Platform fee (15%)" v={pkr(fee)}/>
          <KV k="Your payout" v={<strong className="text-primary">{pkr(myShare)}</strong>}/>
        </dl>
        <p className="text-xs text-muted-foreground mb-3">Confirm the weight and amount to release your payout, or dispute it to freeze payment and alert the admin.</p>
        <div className="flex gap-2">
          <Button onClick={()=>dispatch({type:'verify',jobId:j.id})}><CheckCircle2/>Yes, pay out</Button>
          <Button variant="outline" onClick={()=>dispatch({type:'dispute',jobId:j.id,note:'Farmer disputed weight via portal.'})}><Gavel/>Dispute</Button>
        </div>
      </article>;
    })}
  </div>

  <SectionTitle title="My lots"/>
  <div className="jobs-grid">
    {mine.map(j=>{
      const lot=state.lots.find(l=>l.id===j.lotId)!;
      const factory=state.factories.find(f=>f.id===j.factoryId);
      // F2: the quote the farmer hears — the same escrow the ledger will book.
      const escrow = factory ? escrowFor(j,lot,factory) : 0;
      return <article className="job-card" key={j.id}>
        <div className="flex justify-between gap-2"><span className="text-xs font-medium text-muted-foreground">{j.id}</span><Pill tone={j.state==='settled'?'live':undefined}>{JOB_STATE_LABEL[j.state]}</Pill></div>
        <h3 className="mt-4">{lot.quantityTonnes} t <span className="text-muted-foreground font-normal">· {RESIDUE_LABEL[lot.residueType]}</span></h3>
        <div className="job-details"><p><MapPin/>{lot.village}, {lot.district}</p><p><FactoryIcon/>{factory?.name??'Matching factories…'}</p><p><CalendarDays/>{lot.pickupWindow}</p></div>
        {factory && <KV k="Quoted escrow" v={pkr(escrow)}/>}
        <JobTracker state={j.state}/>
      </article>;
    })}
    {!mine.length && <div className="empty-state">No lots yet. Report your first residue collection above.</div>}
  </div>

  <div className="loop-note"><span className="loop-note-icon"><Leaf size={23}/></span><div><h3>Small steps. A lasting difference.</h3><p>Your crop residue becomes clean energy, sustainable materials, and healthier soil.</p></div></div>

  <Dialog open={open} onOpenChange={setOpen}><DialogContent className="form-dialog"><DialogTitle>Report residue</DialogTitle><DialogDescription>Same fields our voice agent collects by call (F1). Demo · no real data.</DialogDescription><form onSubmit={onSubmit} className="form-grid">
    <Field label="Residue type"><select name="residue">{RESIDUE_KEYS.map(k=><option key={k} value={k}>{RESIDUE_LABEL[k]}</option>)}</select></Field>
    <Field label="Quantity (tonnes)"><input name="quantity" type="number" min="0.1" step="0.1" defaultValue="2" required/></Field>
    <Field label="District"><select name="district"><option>Sheikhupura</option><option>Gujranwala</option><option>Faisalabad</option><option>Lahore</option></select></Field>
    <Field label="Village"><input name="village" defaultValue="Muridke" required/></Field>
    <Field label="Pickup date"><input name="date" type="date" defaultValue="2026-10-17" required/></Field>
    <div className="col-span-full flex justify-end gap-2"><Button type="button" variant="outline" onClick={()=>setOpen(false)}>Cancel</Button><Button type="submit"><Plus/>Report residue</Button></div>
  </form></DialogContent></Dialog></>;
}

/* ================================================================== *
 * T1 · T2 — Transporter Dashboard
 * ================================================================== */
export function TransporterDashboard(){
  const { state, dispatch } = useDomain();
  const me = state.transporters.find(t=>t.id==='t1')!; // demo driver
  const [now,setNow]=useState(()=>Date.now());
  // Live countdown so offer expiry (A2) is visible without a page reload.
  useEffect(()=>{const id=setInterval(()=>setNow(Date.now()),1000);return ()=>clearInterval(id);},[]);
  const offers = state.offers.filter(o=>o.transporterId===me.id);
  const pending = offers.filter(o=>o.status==='pending');
  const myJobs = state.jobs.filter(j=>j.transporterId===me.id);
  const inMotion = myJobs.filter(j=>['accepted','picked_up'].includes(j.state));

  return <><PageHeading eyebrow="TRANSPORTER DASHBOARD" title="Move harvests forward." description="Connect farms to factories. Every delivery closes the loop."/>
  <div className="stats-grid three">
    <Stat label="Offers to me" value={pending.length} icon={Package} note="Accept before the timer lapses"/>
    <Stat label="Active pickups" value={inMotion.length} icon={Truck} note="Accepted and in motion" tone="gold"/>
    <Stat label="Completed deliveries" value={myJobs.filter(j=>['delivered','confirmed','verified','settled'].includes(j.state)).length} icon={CheckCircle2} note="Delivered to partner factories"/>
  </div>

  <SectionTitle title="Offers for you (T1)"/>
  <div className="jobs-grid">
    {pending.map(o=>{
      const job=state.jobs.find(j=>j.id===o.jobId)!;
      const lot=state.lots.find(l=>l.id===job.lotId)!;
      const factory=state.factories.find(f=>f.id===job.factoryId)!;
      const pay=Math.round(lot.quantityTonnes*TRANSPORT_RATE_PER_TONNE);
      const msLeft=Math.max(0,o.expiresAt-now);
      const mm=String(Math.floor(msLeft/60000)).padStart(2,'0');
      const ss=String(Math.floor((msLeft%60000)/1000)).padStart(2,'0');
      return <article className="job-card" key={o.id}>
        <div className="flex justify-between gap-2"><span className="text-xs font-medium text-muted-foreground">{o.jobId}</span><Pill tone={msLeft>0?'gold':'live'}><span className="countdown">{msLeft>0?`${mm}:${ss}`:'Lapsed'}</span></Pill></div>
        <h3 className="mt-4">{lot.quantityTonnes} t <span className="text-muted-foreground font-normal">· {RESIDUE_LABEL[lot.residueType]}</span></h3>
        <div className="job-details"><p><MapPin/>Pickup: {lot.village}, {lot.district}</p><p><FactoryIcon/>{factory.name}</p></div>
        <KV k="Your pay" v={<strong className="text-primary">{pkr(pay)}</strong>}/>
        <Button onClick={()=>dispatch({type:'acceptOffer',offerId:o.id})} disabled={msLeft===0}>Accept job <ArrowRight/></Button>
      </article>;
    })}
    {!pending.length && <div className="empty-state">No open offers right now. New factory-funded jobs appear here.</div>}
  </div>

  <SectionTitle title="My jobs (T2)"/>
  <div className="jobs-grid">
    {myJobs.map(j=>{
      const lot=state.lots.find(l=>l.id===j.lotId)!;
      const pay=Math.round(lot.quantityTonnes*TRANSPORT_RATE_PER_TONNE);
      const released=state.ledger.some(e=>e.jobId===j.id&&e.kind==='release_transporter');
      return <article className="job-card" key={j.id}>
        <div className="flex justify-between gap-2"><span className="text-xs font-medium text-muted-foreground">{j.id}</span><Pill tone={released?'live':undefined}>{released?'Paid':'Payout pending'}</Pill></div>
        <h3 className="mt-4">{lot.quantityTonnes} t <span className="text-muted-foreground font-normal">· {RESIDUE_LABEL[lot.residueType]}</span></h3>
        <div className="job-details"><p><MapPin/>{lot.village}, {lot.district}</p></div>
        <KV k="Pay on delivery" v={pkr(pay)}/>
        <JobTracker state={j.state}/>
        {j.state==='accepted' && <Button className="mt-3" onClick={()=>dispatch({type:'pickup',jobId:j.id,photoRef:`pickup-${j.id}.jpg`,weightTonnes:lot.quantityTonnes})}><Camera/>Record pickup</Button>}
        {j.state==='picked_up' && <Button className="mt-3" onClick={()=>dispatch({type:'deliver',jobId:j.id,photoRef:`delivery-${j.id}.jpg`,weightTonnes:lot.quantityTonnes})}><CheckCircle2/>Record delivery</Button>}
      </article>;
    })}
    {!myJobs.length && <div className="empty-state">Accept an offer to start a job.</div>}
  </div></>;
}

/* ================================================================== *
 * FA1 · FA2 · FA3 — Factory Dashboard
 * ================================================================== */
export function FactoryDashboard(){
  const { state, dispatch } = useDomain();
  const me = state.factories.find(f=>f.id==='fac1')!; // demo factory
  const [open,setOpen]=useState(false);
  // Scoped to this factory (fac1 = GreenCycle). The seed spreads jobs across
  // factories, so an unscoped list would show one factory's work under
  // another's heading.
  const jobs = state.jobs.filter(j=>j.factoryId===me.id);
  const awaitingFunding = jobs.filter(j=>j.state==='created');
  const funded = jobs.filter(j=>j.state==='funded');
  const atGate = jobs.filter(j=>j.state==='delivered');
  const inventory = jobs.filter(j=>['confirmed','verified','settled'].includes(j.state)).reduce((n,j)=>n+(j.finalWeightTonnes??0),0);
  const products = state.products.filter(p=>p.factoryId===me.id);
  const orders = state.orders.filter(o=>{
    const p = state.products.find(x=>x.id===o.productId);
    return p?.factoryId === me.id;
  });

  function addProduct(e:FormEvent<HTMLFormElement>){
    e.preventDefault();
    const d=new FormData(e.currentTarget);
    dispatch({type:'addProduct',factoryId:me.id,name:String(d.get('name')),category:String(d.get('category')),
      priceCents:Math.round(Number(d.get('price'))*100),unit:String(d.get('unit')),description:String(d.get('desc')),image:field});
    setOpen(false);
  }

  return <><PageHeading eyebrow={`FACTORY DASHBOARD · ${me.name.toUpperCase()}`} title="From residue to resources." description="Fund escrow, confirm weights, and bring sustainable products to life." action={<Button onClick={()=>setOpen(true)}><Plus/>Add product</Button>}/>
  <div className="stats-grid">
    <Stat label="Awaiting escrow" value={awaitingFunding.length} icon={Banknote} note="Fund to start dispatch (FA1)"/>
    <Stat label="At the weighbridge" value={atGate.length} icon={Scale} note="Confirm or reject (FA2)" tone="gold"/>
    <Stat label="Raw material in" value={`${inventory.toFixed(1)} t`} icon={Wheat} note="Confirmed and received"/>
    <Stat label="Products listed" value={products.filter(p=>p.listed).length} icon={Package} note="In the marketplace"/>
  </div>

  {awaitingFunding.length>0 && <SectionTitle title="Fund escrow to start dispatch (FA1)"/>}
  <div className="jobs-grid">
    {awaitingFunding.map(j=>{
      const lot=state.lots.find(l=>l.id===j.lotId)!;
      const escrow=escrowFor(j,lot,me);
      return <article className="job-card" key={j.id}>
        <div className="flex justify-between gap-2"><span className="text-xs font-medium text-muted-foreground">{j.id}</span><Pill>Awaiting funds</Pill></div>
        <h3 className="mt-4">{lot.quantityTonnes} t <span className="text-muted-foreground font-normal">· {RESIDUE_LABEL[lot.residueType]}</span></h3>
        <div className="job-details"><p><MapPin/>{lot.village}, {lot.district}</p></div>
        <KV k="Escrow required" v={<strong className="text-primary">{pkr(escrow)}</strong>}/>
        <Button onClick={()=>dispatch({type:'fundEscrow',jobId:j.id})}><Banknote/>Fund escrow</Button>
      </article>;
    })}
  </div>

  {/* A funded job is not yet offered — the factory sends it out to transporters. */}
  {funded.length>0 && <SectionTitle title="Ready to dispatch"/>}
  <div className="jobs-grid">
    {funded.map(j=>{
      const lot=state.lots.find(l=>l.id===j.lotId)!;
      return <article className="job-card" key={j.id}>
        <div className="flex justify-between gap-2"><span className="text-xs font-medium text-muted-foreground">{j.id}</span><Pill tone="gold">Escrow funded</Pill></div>
        <h3 className="mt-4">{lot.quantityTonnes} t <span className="text-muted-foreground font-normal">· {RESIDUE_LABEL[lot.residueType]}</span></h3>
        <JobTracker state={j.state}/>
        <Button className="mt-3" onClick={()=>dispatch({type:'makeOffers',jobId:j.id,nowMs:Date.now()})}><Truck/>Send offer to transporters</Button>
      </article>;
    })}
  </div>

  {atGate.length>0 && <SectionTitle title="Weighbridge — confirm or reject (FA2)"/>}
  <div className="jobs-grid">
    {atGate.map(j=>{
      const lot=state.lots.find(l=>l.id===j.lotId)!;
      return <article className="job-card" key={j.id}>
        <div className="flex justify-between gap-2"><span className="text-xs font-medium text-muted-foreground">{j.id}</span><Pill tone="gold">At gate</Pill></div>
        <h3 className="mt-4">{lot.quantityTonnes} t <span className="text-muted-foreground font-normal">· {RESIDUE_LABEL[lot.residueType]}</span></h3>
        <div className="job-details"><p><Scale/>Delivered weight: {j.finalWeightTonnes} t</p></div>
        <GradeCard grade={{residueType:lot.residueType,moistureBand:'low',contaminationFlags:[],confidence:0.86,disclaimer:'Visual estimate only; weighbridge confirmation required.'}}/>
        <div className="flex gap-2 mt-3">
          <Button onClick={()=>dispatch({type:'confirmWeight',jobId:j.id,grade:{residueType:lot.residueType,moistureBand:'low',contaminationFlags:[],confidence:0.86,disclaimer:'Visual estimate only; weighbridge confirmation required.'}})}><Check/>Confirm weight</Button>
          <Button variant="outline" onClick={()=>dispatch({type:'rejectLot',jobId:j.id,reason:'Moisture above agreed threshold.'})}><X/>Reject lot</Button>
        </div>
      </article>;
    })}
  </div>

  <SectionTitle title="My products (FA3)"/>
  <div className="table-wrap"><table><thead><tr><th>Product</th><th>Price</th><th>Stock</th><th>Listed</th><th></th></tr></thead><tbody>
    {products.map(p=><tr key={p.id}><td className="font-medium">{p.name}<span className="table-sub">{p.unit}</span></td><td>{pkr(p.priceCents)}</td><td>{p.stock}</td><td>{p.listed?'Yes':'No'}</td><td><Button variant="ghost" size="sm" onClick={()=>dispatch({type:'toggleProduct',productId:p.id})}>{p.listed?'Unlist':'List'}</Button></td></tr>)}
  </tbody></table></div>

  <SectionTitle title="Orders & revenue split (B1/FA3)"/>
  <div className="panel-grid">
    {orders.map(o=>{
      const p=state.products.find(x=>x.id===o.productId);
      return <article className="job-card" key={o.id}>
        <div className="flex justify-between gap-2"><span className="text-xs font-medium text-muted-foreground">{o.id}</span><Pill tone="live">Split recorded</Pill></div>
        <h3 className="mt-4">{o.quantity} × {p?.name??'Product'}</h3>
        <KV k="Order total" v={pkr(o.totalCents)}/>
        <SplitBreakdown totalCents={o.totalCents} splitCents={o.splitCents}/>
      </article>;
    })}
    {!orders.length && <div className="empty-state">No orders yet. Buyers create these from the marketplace.</div>}
  </div>

  <Dialog open={open} onOpenChange={setOpen}><DialogContent className="form-dialog"><DialogTitle>Add product</DialogTitle><DialogDescription>Turn confirmed residue into a marketplace product (FA3).</DialogDescription><form onSubmit={addProduct} className="form-grid">
    <Field label="Product name"><input name="name" required/></Field>
    <Field label="Category"><select name="category"><option>Energy</option><option>Farming &amp; Garden</option><option>Building Materials</option></select></Field>
    <Field label="Price (PKR)"><input name="price" type="number" min="1" step="1" required/></Field>
    <Field label="Unit"><input name="unit" defaultValue="per 25 kg bag" required/></Field>
    <Field label="Description"><textarea name="desc" placeholder="What is it made from?"/></Field>
    <div className="col-span-full flex justify-end gap-2"><Button type="button" variant="outline" onClick={()=>setOpen(false)}>Cancel</Button><Button type="submit"><Plus/>Add product</Button></div>
  </form></DialogContent></Dialog></>;
}

/* ================================================================== *
 * A1 · A2 · A3 — Admin Dashboard
 * ================================================================== */
export function AdminDashboard(){
  const { state, dispatch } = useDomain();
  const [resetOpen,setResetOpen]=useState(false);
  const heldCents = state.jobs.filter(j=>j.state!=='settled').reduce((n,j)=>{
    const lot=state.lots.find(l=>l.id===j.lotId); const f=state.factories.find(x=>x.id===j.factoryId);
    return n + (lot&&f? escrowFor(j,lot,f):0);
  },0);
  const settledTonnes = state.jobs.filter(j=>j.state==='settled').reduce((n,j)=>n+(j.finalWeightTonnes??0),0);
  const openEscalations = state.escalations.filter(e=>e.status==='open');

  // A1: rank factories for the newest created lot and allow an override.
  const newestCreated = state.jobs.find(j=>j.state==='created');
  const rankSource = newestCreated && (()=>{
    const lot=state.lots.find(l=>l.id===newestCreated.lotId)!;
    const farmer=state.farmers.find(f=>f.id===lot.farmerId)!;
    return rankFactories(state.factories,{residueType:lot.residueType,lat:farmer.lat,lon:farmer.lon,quantityTonnes:lot.quantityTonnes});
  })();

  return <><PageHeading eyebrow="ADMIN OVERVIEW" title="A growing circular economy." description="One connected view of farms, jobs, factories, and impact." action={<Button variant="outline" onClick={()=>setResetOpen(true)}><RotateCcw/>Reset demo</Button>}/>
  <div className="stats-grid admin-stats">
    <Stat label="Farmers" value={state.farmers.length} icon={Users} note="In the sample records"/>
    <Stat label="Live jobs" value={state.jobs.filter(j=>!['settled','rejected','disputed'].includes(j.state)).length} icon={Truck} note="Across the pipeline" tone="gold"/>
    <Stat label="Transporters" value={state.transporters.length} icon={Truck} note={`${state.transporters.filter(t=>!t.approved).length} awaiting approval`}/>
    <Stat label="Factories" value={state.factories.length} icon={FactoryIcon} note="Processing partners"/>
    <Stat label="Residue kept from burning" value={`${settledTonnes.toFixed(1)} t`} icon={Leaf} note="Settled and verified" tone="gold"/>
    <Stat label="Marketplace orders" value={state.orders.length} icon={ShoppingBag} note="Four-way split recorded"/>
  </div>

  {/* A1 — factory ranking + logged override */}
  {rankSource && newestCreated && <SectionTitle title="Factory ranking and assignment (A1)"/>}
  {rankSource && newestCreated && <div className="table-wrap"><table><thead><tr><th>Rank</th><th>Factory</th><th>Distance</th><th>Price / t</th><th>Score</th><th></th></tr></thead><tbody>
    {rankSource.map((r,i)=><tr key={r.factory.id}>
      <td className="font-medium">{i+1}{r.factory.id===newestCreated.factoryId&&<span className="table-sub">assigned</span>}</td>
      <td>{r.factory.name}</td><td>{r.distanceKm.toFixed(1)} km</td><td>{pkr(r.factory.pricePerTonneCents)}</td><td>{r.score.toFixed(3)}</td>
      <td>{r.factory.id!==newestCreated.factoryId&&<Button variant="ghost" size="sm" onClick={()=>dispatch({type:'assignFactory',jobId:newestCreated.id,factoryId:r.factory.id,override:true})}>Override</Button>}</td>
    </tr>)}
  </tbody></table></div>}

  {/* A2 — offer ladder control + escalations */}
  <div className="admin-panels">
    <section>
      <SectionTitle title="Offer ladder control (A2)"/>
      <div className="chart">
        {state.jobs.filter(j=>['funded','offered'].includes(j.state)).map(j=><div className="chart-row" key={j.id}>
          <span>{j.id}</span>
          <div className="chart-track"><span className="text-xs text-muted-foreground">{j.offeredTransporterIds.length} tried</span></div>
          <Button size="sm" variant="outline" onClick={()=>dispatch({type:'makeOffers',jobId:j.id,nowMs:Date.now()})}>Re-dispatch</Button>
        </div>)}
      </div>
      <p className="text-xs text-muted-foreground mt-2">Re-dispatch advances the transporter ladder; when it is exhausted the job is requeued for you.</p>
      <SectionTitle title="Transporter approvals"/>
      <div className="activity-list">
        {state.transporters.filter(t=>!t.approved).map(t=><div key={t.id}>
          <span className="activity-icon"><ShieldCheck size={15}/></span>
          <div className="flex-1"><p>{t.name} · tier {t.tier}</p><small>Awaiting approval</small></div>
          <Button size="sm" onClick={()=>dispatch({type:'approveTransporter',transporterId:t.id})}>Approve</Button>
        </div>)}
        {state.transporters.every(t=>t.approved)&&<div className="empty-state">All transporters approved.</div>}
      </div>
    </section>
    <section>
      <SectionTitle title="Escalation queue (F3)"/>
      <div className="activity-list">
        {openEscalations.map(e=><div key={e.id}>
          <span className="activity-icon"><Megaphone size={15}/></span>
          <div><p>{e.summary}</p><small>{e.transcript}</small></div>
        </div>)}
        {!openEscalations.length&&<div className="empty-state">No open escalations.</div>}
      </div>
      <SectionTitle title="Recent activity"/>
      <div className="activity-list">
        {state.activity.slice(0,5).map((a,i)=><div key={`${a}-${i}`}><span className="activity-icon"><Leaf size={15}/></span><div><p>{a}</p><small>{i===0?'Latest':'Demo activity'}</small></div></div>)}
      </div>
    </section>
  </div>

  {/* A3 — ledger + invariant */}
  <SectionTitle title="Ledger &amp; escrow invariant (A3)"><DemoLabel/></SectionTitle>
  <LedgerPanel entries={state.ledger} heldCents={heldCents}/>

  <Dialog open={resetOpen} onOpenChange={setResetOpen}><DialogContent><DialogTitle>Reset the demo?</DialogTitle><DialogDescription>This reloads the seed world: one settled job, one offered, one awaiting funding.</DialogDescription><div className="flex justify-end gap-2"><Button variant="outline" onClick={()=>setResetOpen(false)}>Cancel</Button><Button onClick={()=>{dispatch({type:'reset',next:seedDomain()});setResetOpen(false);}}><RotateCcw/>Reset</Button></div></DialogContent></Dialog></>;
}
