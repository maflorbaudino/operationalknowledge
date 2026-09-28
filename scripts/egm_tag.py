# -*- coding: utf-8 -*-
import re, pandas as pd, collections
from egm_load import load

# ---- Temas de intervención (multietiqueta, reglas sobre título + resumen + palabras clave) ----
INT = {
 'Transporte público (bus, BRT, metro, tranvía, teleférico)': r'\b(bus rapid|brt|transit|metro\w*|subway|commuter (?:train|rail)|rapid transit|bus\b|buses|light rail|tram\b|tramway|cable car|gondola|public transport|bus (?:service|lane|network|system|reform|fare|route|stop|priority)|commuter rail|urban rail|rail transit|matatu|minibus|paratransit|transmilenio|metrobus)',
 'Ferrocarril interurbano y alta velocidad': r'(high[- ]speed rail|shinkansen|\bhsr\b|railway|railroad|intercity rail|freight rail|train service|rail line|rail network|rail (?:expansion|connection|access))',
 'Carreteras, autopistas y redes viales': r'(highway|expressway|motorway|freeway|road network|road construction|road infrastructure|new road|road investment|road upgrad|paved road|road improvement|national road|trunk road|road building|interstate|ring road|road expansion|road access|bypass|toll road|\broads\b)',
 'Caminos rurales': r'(rural road|feeder road|village road|rural transport|rural connectivity|rural access|rural infrastructure|pmgsy|road access.{0,40}village|farm[- ]to[- ]market|unpaved road|gravel road|all-weather road)',
 'Mantenimiento vial': r'(road maintenance|maintenance of road|periodic maintenance|routine maintenance|rehabilitation of road|road rehabilitation|pavement|road condition|road quality)',
 'Seguridad vial': r'(road safety|traffic safety|crash|collision|accident|fatalit|speed camera|speed limit|helmet|seat[- ]belt|drunk driving|drink[- ]driving|pedestrian (?:safety|injur|death)|traffic (?:injur|death)|road traffic injur|vision zero|traffic enforcement|traffic law)',
 'Gestión de tráfico, congestión y estacionamiento': r'(congestion|traffic management|traffic flow|parking|low emission zone|\blez\b|driving restriction|license plate|odd[- ]even|road pricing|toll(?:ing|s)?\b|cordon|traffic light|traffic signal|traffic calming|vehicle quota|car[- ]free|pedestrianiz|fuel (?:tax|subsid|price)|vehicle (?:tax|registration|restriction|ban|quota)|pay-as-you-drive|level crossing|driving ban|combustion)',
 'Transporte no motorizado (bicicleta, peatonal)': r'(bicycl|cycling|\bbike|cycle (?:lane|track|path)|pedestrian|walking|walkab|non-motori[sz]ed|bikeshar|bike[- ]shar|e-bike|scooter|active (?:travel|transport|mobility))',
 'Puertos, logística y transporte de carga': r'(\bport\b|\bports\b|seaport|container|logistic|freight|cargo|shipping|maritime|trucking|truck\b|trucks|inland waterway|dry port|border crossing|customs|supply chain|warehous|multimodal|intermodal)',
 'Aviación y aeropuertos': r'(airport|aviation|airline|air (?:transport|travel|service|connectivity|route)|flights?\b|air cargo)',
 'Servicios de movilidad (taxi, ride-hailing, compartida)': r'(ride[- ]?hailing|\buber\b|\blyft\b|\bdidi\b|taxi|ride[- ]shar|car[- ]?shar|carpool|ridesourc|transportation network compan|mobility[- ]as[- ]a[- ]service|shared mobility|motorcycle taxi|mototaxi|rickshaw|tuk[- ]tuk)',
 'Subsidios y tarifas de transporte': r'(fare (?:subsid|discount|free|reduction|integration|policy|structure|increase)|free (?:transit|transport|bus|public transport)|transit subsid|transport subsid|travel (?:voucher|subsid)|\bfares?\b|transport voucher|concession(?:ary)? (?:pass|fare)|public transport pass)',
 'Puentes, túneles y conectividad de redes': r'(bridge|tunnel|ferry|causeway|river crossing|transport corridor|connectivity|transport network)',
 'Reforma institucional, APP y gobernanza': r'(public[- ]private partnership|\bppp\b|privati[sz]|concession|deregulat|regulatory reform|institutional reform|decentrali[sz]|governance|transport (?:authority|agency|reform)|franchis|contracting)',
 'Vehículos eléctricos y transporte limpio': r'(electric vehicle|\bev\b|\bevs\b|electric bus|clean (?:vehicle|transport)|emission standard|fuel economy|vehicle (?:emission|scrappage)|hybrid (?:vehicle|car|bus)|cleaner (?:bus|fuel)|scrappage)',
}
# ---- Resultados ----
OUT = {
 'Empleo, ingresos y mercado laboral': r'(employment|unemployment|labou?r market|\bjobs?\b|wages?\b|earnings|income|labou?r (?:supply|force|participation|market)|commuting to work|worker|occupation|job (?:access|search|matching))',
 'Uso del transporte y cambio modal': r'(ridership|mode (?:choice|share|shift)|modal (?:shift|split)|travel (?:behavio|demand|mode)|patronage|transit use|public transport use|demand for|trip (?:generation|frequency)|vehicle kilomet|vkt|car (?:use|ownership)|bicycle (?:use|trips)|number of trips|mobility patterns|mode substitution|induced (?:demand|travel))',
 'Tiempo de viaje, congestión y velocidad': r'(travel time|commut(?:e|ing) time|congestion|travel speed|delay|journey time|time saving|travel cost|transport cost|trip duration|traffic speed|traffic volume|traffic flow|accessibility|reliability)',
 'Delincuencia y seguridad ciudadana': r'(crime|criminal|violence|theft|robber|homicide|policing|victimi[sz]ation)',
 'Seguridad vial y siniestralidad': r'(crash|collision|accident|fatalit|injur|road safety|traffic safety|casualt|mortality.{0,40}(?:road|traffic))',
 'Calidad del aire, emisiones y ambiente': r'(air quality|pollution|emission|\bpm2\.?5|\bpm10|\bco2|greenhouse|carbon|noise|deforestation|environmental (?:impact|effect|quality)|nitrogen|ozone|particulate|energy consumption|climate)',
 'Valor de la propiedad, vivienda y uso del suelo': r'(property (?:value|price)|house price|housing (?:price|value|market)|land (?:value|price|use|market)|rent(?:s|al)?\b|real estate|urban(?:i[sz]ation| sprawl| form| growth| expansion)|suburbani[sz]ation|residential (?:sorting|location|choice)|gentrif|density|population (?:growth|density|distribution)|city (?:growth|size)|migration)',
 'Actividad económica, comercio y productividad': r'(gdp|economic (?:growth|activity|development|output)|productivity|trade\b|firm (?:entry|performance|growth|location|outcome)|firms\b|industrial|manufactur|market access|regional (?:development|growth|inequal)|economic geography|night ?lights|agglomeration|exports?\b|business (?:activity|growth|performance)|prices? (?:dispersion|convergence)|market integration|tourism)',
 'Acceso a servicios (salud, educación, mercados)': r'(school|education|enrol|attendance|hospital|health (?:care|service|facilit|access|outcome)|clinic|access to (?:health|school|market|service|education|hospital|facilit)|maternal|literacy|student|childbirth|health\b)',
 'Agricultura y precios rurales': r'(agricultur|farm|crop|rural (?:household|income|poverty|economy|market|development)|village|harvest|agrarian|food (?:price|security)|livestock|yield)',
 'Pobreza, bienestar y equidad': r'(poverty|welfare|inequalit|equity|well-?being|consumption|living standard|deprivation|social exclusion|gender|women|female|vulnerable|distribution(?:al)? (?:effect|impact))',
 'Costos, eficiencia y rentabilidad de la inversión': r'(cost[- ]benefit|benefit[- ]cost|cost[- ]effective|return on investment|rate of return|efficiency|operating cost|value for money|project cost|cost overrun|financial (?:performance|viability)|economic (?:appraisal|evaluation|return)|social return)',
}
# ---- Diseño ----
DES = {
 'Ensayo aleatorizado (RCT / experimento de campo)': r'(randomi[sz]ed|randomly assigned|randomi[sz]ation|\brct\b|field experiment|lottery|random assignment|experimental evidence|natural field experiment)',
 'Cuasi-experimental (DiD, RD, VI, PSM, control sintético)': r'(difference[- ]in[- ]difference|\bdid\b|regression discontinuity|\brdd?\b|instrumental variable|\biv\b|propensity score|synthetic control|quasi[- ]experiment|natural experiment|event study|matching (?:estimator|method)|placebo|counterfactual|two[- ]way fixed|staggered|exogenous variation|identification strategy|panel data|fixed effects|before[- ]and[- ]after|pre[- ]post)',
 'Revisión sistemática / metaanálisis': r'(systematic review|meta[- ]analysis|meta-regression|evidence (?:review|synthesis)|literature review|scoping review|review of (?:the )?(?:evidence|literature)|rapid evidence)',
 'Simulación / modelo estructural o de equilibrio': r'(simulation|structural model|general equilibrium|spatial equilibrium|counterfactual (?:scenario|simulation)|calibrat|quantitative (?:spatial )?model|agent-based|computable|cge\b)',
}
# ---- Países y regiones ----
C = {  # país (nombre en español): (región, patrón)
 'Brasil':('ALC',r'brazil|brasil|são paulo|sao paulo|rio de janeiro|curitiba|belo horizonte|(?-i:(?<!El )\bSalvador\b)|fortaleza|recife|porto alegre|brasília'),
 'Colombia':('ALC',r'colombia|bogot|medell[ií]n|(?-i:\bCali\b)|barranquilla|cartagena|transmilenio|pereira|bucaramanga'),
 'México':('ALC',r'mexic|guadalajara|monterrey|tijuana'),
 'Argentina':('ALC',r'argentin|buenos aires|c[oó]rdoba, arg|rosario'),
 'Chile':('ALC',r'\bchile|santiago de chile|transantiago|santiago\b|valpara'),
 'Perú':('ALC',r'\bperu\b|peruvian|(?-i:\bLima\b)'),
 'Ecuador':('ALC',r'ecuador|quito|guayaquil'),
 'Bolivia':('ALC',r'bolivia|la paz\b|el alto'),
 'Uruguay':('ALC',r'uruguay|montevideo'),
 'Paraguay':('ALC',r'paraguay|asunci[oó]n'),
 'Venezuela':('ALC',r'venezuela|caracas'),
 'Guatemala':('ALC',r'guatemala'),
 'Honduras':('ALC',r'honduras'),
 'Nicaragua':('ALC',r'nicaragua'),
 'El Salvador':('ALC',r'el salvador|salvadoran'),
 'Costa Rica':('ALC',r'costa rica'),
 'Panamá':('ALC',r'panama\b|panam[aá]'),
 'Haití':('ALC',r'haiti'),
 'República Dominicana':('ALC',r'dominican republic|santo domingo'),
 'Jamaica':('ALC',r'jamaica'),
 'Guyana':('ALC',r'guyana'),
 'Belice':('ALC',r'belize'),
 'Surinam':('ALC',r'suriname'),
 'Bahamas':('ALC',r'bahamas'),
 'Cuba':('ALC',r'\bcuba\b'),
 'Latinoamérica y Caribe (regional)':('ALC',r'latin america|caribbean'),
 'Estados Unidos':('Norteamérica',r'united states|(?-i:\bUSA?\b|\bU\.S\.)|american cit|new york|los angeles|chicago|boston|san francisco|california|texas|portland|seattle|washington,? d|columbus|philadelphia|atlanta|minneapolis|denver|houston'),
 'Canadá':('Norteamérica',r'canad|toronto|vancouver|winnipeg|montreal|calgary|ontario|quebec'),
 'China':('Asia',r'\bchina\b|chinese|beijing|shanghai|shenzhen|guangzhou|hong kong|chengdu|wuhan|hangzhou|nanjing'),
 'India':('Asia',r'\bindia\b|indian\b|delhi|mumbai|bangalore|bengaluru|chennai|kolkata|pmgsy|hyderabad|ahmedabad|kerala|bihar|rajasthan'),
 'Japón':('Asia',r'japan|tokyo|osaka|shinkansen'),
 'Corea del Sur':('Asia',r'\bkorea|seoul'),
 'Taiwán':('Asia',r'taiwan|taipei'),
 'Indonesia':('Asia',r'indonesia|jakarta'),
 'Vietnam':('Asia',r'vietnam|hanoi|ho chi minh'),
 'Tailandia':('Asia',r'thailand|bangkok'),
 'Filipinas':('Asia',r'philippine|manila'),
 'Malasia':('Asia',r'malaysia|kuala lumpur'),
 'Singapur':('Asia',r'singapore'),
 'Bangladés':('Asia',r'bangladesh|dhaka'),
 'Pakistán':('Asia',r'pakistan|lahore|karachi'),
 'Sri Lanka':('Asia',r'sri lanka'),
 'Nepal':('Asia',r'\bnepal'),
 'Camboya / Laos / Myanmar':('Asia',r'cambodia|laos|(?-i:\bLao\b)|myanmar'),
 'Turquía':('Asia',r'turkey|t[uü]rk|istanbul|ankara'),
 'Irán / Israel / Golfo':('Asia',r'\biran\b|israel|saudi|dubai|qatar|lebanon'),
 'Kazajistán / Asia Central':('Asia',r'kazakh|uzbek|central asia|mongolia|kyrgyz'),
 'Reino Unido':('Europa',r'united kingdom|\buk\b|london|england|britain|british|scotland|manchester'),
 'Alemania':('Europa',r'german|berlin|munich|hamburg'),
 'Francia':('Europa',r'france|french|paris\b'),
 'España':('Europa',r'spain|spanish|madrid|barcelona'),
 'Italia':('Europa',r'ital(?:y|ian)|milan|(?-i:\bRome\b)'),
 'Países Bajos / Bélgica':('Europa',r'netherlands|dutch|amsterdam|belgi'),
 'Escandinavia':('Europa',r'sweden|swedish|stockholm|denmark|danish|copenhagen|norway|norwegian|oslo|finland'),
 'Europa Central y del Este':('Europa',r'poland|polish|czech|hungar|romania|bulgaria|russia|ukraine|serbia|croatia|slovenia|austria|switzerland|swiss|portug|greece|greek|ireland|europe'),
 'Sudáfrica':('África',r'south africa|cape town|johannesburg'),
 'Kenia':('África',r'kenya|nairobi'),
 'Etiopía':('África',r'ethiopia|addis'),
 'Tanzania / Uganda / Ruanda':('África',r'tanzania|uganda|rwanda|kampala|dar es salaam'),
 'Nigeria / Ghana':('África',r'nigeria|ghana|lagos|accra'),
 'Otros países de África':('África',r'africa|senegal|(?-i:\bMali\b)|zambia|malawi|mozambique|zimbabwe|botswana|namibia|cameroon|congo|sierra leone|liberia|burkina|(?-i:\bNiger\b)|madagascar|morocco|egypt|tunisia|algeria|sudan|benin|angola|lesotho|togo'),
 'Australia / Nueva Zelanda / Pacífico':('Oceanía',r'australia|new zealand|sydney|melbourne|auckland|pacific island|fiji|papua'),
}
CRX={k:re.compile(v[1],re.I) for k,v in C.items()}
IX={k:re.compile(v,re.I) for k,v in INT.items()}; OX={k:re.compile(v,re.I) for k,v in OUT.items()}; DX={k:re.compile(v,re.I) for k,v in DES.items()}

def tag(df):
    rows=[]
    for _,r in df.iterrows():
        title=str(r.Title); abst='' if pd.isna(r.Abstract) else str(r.Abstract); kw=r.kw
        clean=lambda x:re.sub(r'(?:low|middle|high|lower|upper)[- ](?:and[- ](?:middle|low|high|upper)[- ])?income','',x,flags=re.I)
        title,abst,kw=clean(title),clean(abst),clean(kw)
        full=' '.join([title,abst,kw])
        # intervención: título y keywords pesan más; se exige >=1 mención en título/kw o >=2 en el resumen
        iv=[]
        for k,x in IX.items():
            t=len(x.findall(title+' '+kw)); a=len(x.findall(abst))
            if t>=1 or a>=3: iv.append((k,t*3+a))
        iv=[k for k,s in sorted(iv,key=lambda z:-z[1])]
        STRONG=re.compile(r'highway|expressway|motorway|freeway|interstate|trunk road|toll road|ring road|national road|bypass|beltway|autobahn',re.I)
        RUR='Caminos rurales'; CAR='Carreteras, autopistas y redes viales'
        if RUR in iv and CAR in iv and not STRONG.search(full): iv.remove(CAR)
        if not iv and re.search(r'infrastructure|transport(?:ation)? (?:investment|project|system)|public works',title+' '+kw+' '+abst,re.I): iv=['Infraestructura de transporte (general)']
        ou=[k for k,x in OX.items() if len(x.findall(title+' '+kw))>=1 or len(x.findall(abst))>=2]
        de=[k for k,x in DX.items() if x.search(full)]
        # países: título+keywords primero; si no, resumen (>=1 mención)
        ct=[k for k,x in CRX.items() if x.search(title+' '+kw)] or [k for k,x in CRX.items() if x.search(abst)]
        # Ambigüedad conocida: 'Santiago', 'salvador', 'cali' etc. quedan sujetos a revisión de muestra
        reg=sorted({C[k][0] for k in ct})
        rows.append(dict(intervenciones=iv,resultados=ou,disenos=de,paises=ct,regiones=reg))
    return pd.DataFrame(rows)

if __name__=='__main__':
    df,_=load(); t=tag(df); d=pd.concat([df,t],axis=1)
    for c in ['intervenciones','resultados','disenos','paises','regiones']:
        cnt=collections.Counter(x for L in d[c] for x in L); print('\n==',c,'sin etiqueta:',(d[c].str.len()==0).sum()); [print(f'  {n:4d} {k}') for k,n in cnt.most_common(40)]
    d.to_pickle('egm_tagged.pkl')
