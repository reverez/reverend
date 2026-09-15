'use strict';
(function(root,factory){
  const api=factory();
  if(typeof module==='object'&&module.exports)module.exports=api;
  if(root){
    root.parseReverendDiagram=api.parseReverendDiagram;
    root.renderReverendDiagram=api.renderReverendDiagram;
  }
})(typeof window!=='undefined'?window:null,function(){
  const MAX_SOURCE=12000;
  const MAX_NODES=40;
  const MAX_EDGES=80;
  let renderCounter=0;

  function cleanLabel(value,fallback){
    let text=String(value||fallback||'').trim();
    if(
      (text.startsWith('"')&&text.endsWith('"'))||
      (text.startsWith("'")&&text.endsWith("'"))
    )text=text.slice(1,-1).trim();
    if(!text||text.length>180||/[\x00-\x08\x0B\x0C\x0E-\x1F]/.test(text))
      throw new Error('Diagram label is invalid or too long');
    return text;
  }

  function parseNode(token){
    const value=String(token||'').trim();
    let match=value.match(/^([A-Za-z][A-Za-z0-9_-]{0,63})\[([^\]]{1,180})\]$/);
    if(match)return {id:match[1],label:cleanLabel(match[2],match[1]),shape:'rect'};
    match=value.match(/^([A-Za-z][A-Za-z0-9_-]{0,63})\{([^}]{1,180})\}$/);
    if(match)return {id:match[1],label:cleanLabel(match[2],match[1]),shape:'decision'};
    match=value.match(/^([A-Za-z][A-Za-z0-9_-]{0,63})\(([^)]{1,180})\)$/);
    if(match)return {id:match[1],label:cleanLabel(match[2],match[1]),shape:'round'};
    match=value.match(/^([A-Za-z][A-Za-z0-9_-]{0,63})$/);
    if(match)return {id:match[1],label:match[1],shape:'rect'};
    throw new Error('Unsupported Mermaid node syntax');
  }

  function parseReverendDiagram(source){
    if(typeof source!=='string'||!source.trim()||source.length>MAX_SOURCE)
      throw new Error('Diagram source is empty or exceeds the safe limit');
    const lines=source.split(/\r?\n/).map(line=>line.trim()).filter(line=>line&&!line.startsWith('%%'));
    if(!lines.length)throw new Error('Diagram source is empty');
    const header=lines.shift().match(/^(?:flowchart|graph)\s+(TD|TB|LR|RL)$/i);
    if(!header)throw new Error('Only Mermaid flowchart/graph TD, TB, LR, or RL is supported');
    const direction=header[1].toUpperCase();
    const nodes=new Map();
    const edges=[];
    function remember(node){
      const previous=nodes.get(node.id);
      if(previous){
        if(previous.label===previous.id&&node.label!==node.id)nodes.set(node.id,node);
        return;
      }
      if(nodes.size>=MAX_NODES)throw new Error('Diagram exceeds the 40-node limit');
      nodes.set(node.id,node);
    }
    for(const line of lines){
      const edge=line.match(/^(.+?)\s*-->\s*(?:\|([^|]{1,80})\|\s*)?(.+)$/);
      if(edge){
        if(edges.length>=MAX_EDGES)throw new Error('Diagram exceeds the 80-edge limit');
        const from=parseNode(edge[1]);
        const to=parseNode(edge[3]);
        remember(from);remember(to);
        edges.push({from:from.id,to:to.id,label:edge[2]?cleanLabel(edge[2],''):''});
        continue;
      }
      remember(parseNode(line));
    }
    if(!nodes.size)throw new Error('Diagram contains no supported nodes');
    return {direction,nodes:[...nodes.values()],edges};
  }

  function layout(spec){
    const indegree=new Map(spec.nodes.map(node=>[node.id,0]));
    const outgoing=new Map(spec.nodes.map(node=>[node.id,[]]));
    for(const edge of spec.edges){
      indegree.set(edge.to,(indegree.get(edge.to)||0)+1);
      outgoing.get(edge.from).push(edge.to);
    }
    const ranks=new Map(spec.nodes.map(node=>[node.id,0]));
    const queue=spec.nodes.filter(node=>(indegree.get(node.id)||0)===0).map(node=>node.id);
    const visited=new Set();
    while(queue.length){
      const id=queue.shift();visited.add(id);
      for(const target of outgoing.get(id)||[]){
        ranks.set(target,Math.max(ranks.get(target)||0,(ranks.get(id)||0)+1));
        indegree.set(target,(indegree.get(target)||0)-1);
        if(indegree.get(target)===0)queue.push(target);
      }
    }
    let fallback=Math.max(0,...ranks.values());
    for(const node of spec.nodes)if(!visited.has(node.id))ranks.set(node.id,++fallback);
    const groups=new Map();
    for(const node of spec.nodes){
      const rank=ranks.get(node.id)||0;
      if(!groups.has(rank))groups.set(rank,[]);
      groups.get(rank).push(node);
    }
    const positions=new Map();
    const NODE_W=164,NODE_H=56,GAP_X=58,GAP_Y=48,PAD=34;
    const horizontal=spec.direction==='LR'||spec.direction==='RL';
    let maxAcross=1,maxRank=0;
    for(const [rank,items] of groups){maxRank=Math.max(maxRank,rank);maxAcross=Math.max(maxAcross,items.length);}
    const width=horizontal?PAD*2+(maxRank+1)*(NODE_W+GAP_X)-GAP_X:PAD*2+maxAcross*(NODE_W+GAP_X)-GAP_X;
    const height=horizontal?PAD*2+maxAcross*(NODE_H+GAP_Y)-GAP_Y:PAD*2+(maxRank+1)*(NODE_H+GAP_Y)-GAP_Y;
    for(const [rank,items] of groups){
      items.forEach((node,index)=>{
        let x,y;
        if(horizontal){
          const resolved=spec.direction==='RL'?maxRank-rank:rank;
          x=PAD+resolved*(NODE_W+GAP_X);y=PAD+index*(NODE_H+GAP_Y);
        }else{
          x=PAD+index*(NODE_W+GAP_X);y=PAD+rank*(NODE_H+GAP_Y);
        }
        positions.set(node.id,{x,y,w:NODE_W,h:NODE_H});
      });
    }
    return {positions,width,height};
  }

  function svgEl(name,attrs={}){
    const el=document.createElementNS('http://www.w3.org/2000/svg',name);
    for(const [key,value] of Object.entries(attrs))el.setAttribute(key,String(value));
    return el;
  }

  function renderReverendDiagram(source){
    if(typeof document==='undefined')throw new Error('Diagram rendering requires a browser document');
    const spec=parseReverendDiagram(source);
    const layoutResult=layout(spec);
    const shell=document.createElement('div');shell.className='diagram-canvas';
    const svg=svgEl('svg',{viewBox:`0 0 ${layoutResult.width} ${layoutResult.height}`,role:'img','aria-label':'Flowchart diagram'});
    const defs=svgEl('defs');
    const markerId='reverend-arrow-'+(++renderCounter);
    const marker=svgEl('marker',{id:markerId,viewBox:'0 0 10 10',refX:9,refY:5,markerWidth:7,markerHeight:7,orient:'auto-start-reverse'});
    marker.append(svgEl('path',{d:'M 0 0 L 10 5 L 0 10 z',class:'diagram-arrow'}));defs.append(marker);svg.append(defs);
    for(const edge of spec.edges){
      const a=layoutResult.positions.get(edge.from),b=layoutResult.positions.get(edge.to);if(!a||!b)continue;
      const horizontal=spec.direction==='LR'||spec.direction==='RL';
      const x1=horizontal?(b.x>=a.x?a.x+a.w:a.x):a.x+a.w/2;
      const y1=horizontal?a.y+a.h/2:(b.y>=a.y?a.y+a.h:a.y);
      const x2=horizontal?(b.x>=a.x?b.x:b.x+b.w):b.x+b.w/2;
      const y2=horizontal?b.y+b.h/2:(b.y>=a.y?b.y:b.y+b.h);
      svg.append(svgEl('line',{x1,y1,x2,y2,class:'diagram-edge','marker-end':`url(#${markerId})`}));
      if(edge.label){
        const label=svgEl('text',{x:(x1+x2)/2,y:(y1+y2)/2-7,class:'diagram-edge-label','text-anchor':'middle'});
        label.textContent=edge.label;svg.append(label);
      }
    }
    for(const node of spec.nodes){
      const p=layoutResult.positions.get(node.id);const group=svgEl('g',{class:'diagram-node'});
      if(node.shape==='decision'){
        group.append(svgEl('polygon',{points:`${p.x+p.w/2},${p.y} ${p.x+p.w},${p.y+p.h/2} ${p.x+p.w/2},${p.y+p.h} ${p.x},${p.y+p.h/2}`,class:'diagram-node-shape'}));
      }else{
        group.append(svgEl('rect',{x:p.x,y:p.y,width:p.w,height:p.h,rx:node.shape==='round'?28:10,class:'diagram-node-shape'}));
      }
      const text=svgEl('text',{x:p.x+p.w/2,y:p.y+p.h/2,class:'diagram-node-label','text-anchor':'middle','dominant-baseline':'middle'});
      const words=node.label.split(/\s+/);const lines=[];let current='';
      for(const word of words){const next=(current+' '+word).trim();if(next.length>26&&current){lines.push(current);current=word;}else current=next;}if(current)lines.push(current);
      const visible=lines.slice(0,2);visible.forEach((line,index)=>{const tspan=svgEl('tspan',{x:p.x+p.w/2,dy:index===0?(visible.length===2?-8:0):16});tspan.textContent=line;text.append(tspan);});
      group.append(text);svg.append(group);
    }
    shell.append(svg);return shell;
  }

  return {parseReverendDiagram,renderReverendDiagram};
});
