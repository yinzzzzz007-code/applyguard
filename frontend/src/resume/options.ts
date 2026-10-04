/** Option dictionaries aligned with campus-resume style (join.qq.com / HR dicts). */

export const GENDER_OPTIONS = ['男', '女']

export const POLITICS_OPTIONS = [
  '中共党员',
  '中共预备党员',
  '共青团员',
  '民革会员',
  '民盟盟员',
  '民建会员',
  '民进会员',
  '农工党党员',
  '致公党党员',
  '九三学社社员',
  '台盟盟员',
  '无党派人士',
  '群众',
]

export const ETHNICITY_OPTIONS = [
  '汉族',
  '蒙古族',
  '回族',
  '藏族',
  '维吾尔族',
  '苗族',
  '彝族',
  '壮族',
  '布依族',
  '朝鲜族',
  '满族',
  '侗族',
  '瑶族',
  '白族',
  '土家族',
  '哈尼族',
  '哈萨克族',
  '傣族',
  '黎族',
  '傈僳族',
  '佤族',
  '畲族',
  '高山族',
  '拉祜族',
  '水族',
  '东乡族',
  '纳西族',
  '景颇族',
  '柯尔克孜族',
  '土族',
  '达斡尔族',
  '仫佬族',
  '羌族',
  '布朗族',
  '撒拉族',
  '毛南族',
  '仡佬族',
  '锡伯族',
  '阿昌族',
  '普米族',
  '塔吉克族',
  '怒族',
  '乌孜别克族',
  '俄罗斯族',
  '鄂温克族',
  '德昂族',
  '保安族',
  '裕固族',
  '京族',
  '塔塔尔族',
  '独龙族',
  '鄂伦春族',
  '赫哲族',
  '门巴族',
  '珞巴族',
  '基诺族',
]

export const ID_TYPE_OPTIONS = [
  '居民身份证',
  '护照',
  '港澳居民来往内地通行证',
  '台湾居民来往大陆通行证',
  '外国人永久居留身份证',
  '其他',
]

export const DEGREE_OPTIONS = [
  '博士研究生',
  '硕士研究生',
  '本科',
  '专科',
  '高职',
  '中专/高中',
  '其他',
]

export const FULL_TIME_OPTIONS = ['是', '否']

export const PROJECT_TYPE_OPTIONS = ['应届生', '实习生', '社招（演示）']

/** Province → cities (simplified China mainland set for cascader demos). */
export const REGION_TREE: Record<string, string[]> = {
  北京市: ['东城区', '西城区', '朝阳区', '海淀区', '丰台区', '石景山区', '通州区', '昌平区', '大兴区', '其他'],
  上海市: ['黄浦区', '徐汇区', '长宁区', '静安区', '普陀区', '虹口区', '杨浦区', '浦东新区', '闵行区', '宝山区', '嘉定区', '其他'],
  天津市: ['和平区', '河东区', '河西区', '南开区', '河北区', '红桥区', '滨海新区', '其他'],
  重庆市: ['渝中区', '江北区', '南岸区', '沙坪坝区', '九龙坡区', '渝北区', '其他'],
  广东省: ['广州市', '深圳市', '珠海市', '佛山市', '东莞市', '中山市', '惠州市', '湛江市', '其他'],
  浙江省: ['杭州市', '宁波市', '温州市', '嘉兴市', '绍兴市', '金华市', '其他'],
  江苏省: ['南京市', '苏州市', '无锡市', '常州市', '南通市', '徐州市', '其他'],
  山东省: ['济南市', '青岛市', '烟台市', '潍坊市', '临沂市', '其他'],
  福建省: ['福州市', '厦门市', '泉州市', '漳州市', '其他'],
  湖南省: ['长沙市', '株洲市', '湘潭市', '其他'],
  湖北省: ['武汉市', '宜昌市', '襄阳市', '其他'],
  四川省: ['成都市', '绵阳市', '德阳市', '其他'],
  河南省: ['郑州市', '洛阳市', '开封市', '其他'],
  河北省: ['石家庄市', '唐山市', '保定市', '其他'],
  安徽省: ['合肥市', '芜湖市', '其他'],
  江西省: ['南昌市', '赣州市', '其他'],
  辽宁省: ['沈阳市', '大连市', '其他'],
  吉林省: ['长春市', '吉林市', '其他'],
  黑龙江省: ['哈尔滨市', '大庆市', '其他'],
  陕西省: ['西安市', '咸阳市', '其他'],
  山西省: ['太原市', '其他'],
  云南省: ['昆明市', '其他'],
  贵州省: ['贵阳市', '其他'],
  广西壮族自治区: ['南宁市', '桂林市', '柳州市', '其他'],
  海南省: ['海口市', '三亚市', '其他'],
  内蒙古自治区: ['呼和浩特市', '包头市', '其他'],
  新疆维吾尔自治区: ['乌鲁木齐市', '其他'],
  西藏自治区: ['拉萨市', '其他'],
  宁夏回族自治区: ['银川市', '其他'],
  青海省: ['西宁市', '其他'],
  甘肃省: ['兰州市', '其他'],
  香港特别行政区: ['香港岛', '九龙', '新界'],
  澳门特别行政区: ['澳门半岛', '氹仔', '路环'],
  台湾省: ['台北市', '高雄市', '其他'],
  海外: ['其他'],
}

export const PROVINCES = Object.keys(REGION_TREE)

export function yearsBetween(from: number, to: number): string[] {
  const out: string[] = []
  for (let y = to; y >= from; y -= 1) out.push(String(y))
  return out
}

export const YEAR_OPTIONS = yearsBetween(1970, new Date().getFullYear())
export const MONTH_OPTIONS = Array.from({ length: 12 }, (_, i) => String(i + 1).padStart(2, '0'))
export function dayOptions(year: string, month: string): string[] {
  const y = Number(year)
  const m = Number(month)
  if (!y || !m) return Array.from({ length: 31 }, (_, i) => String(i + 1).padStart(2, '0'))
  const count = new Date(y, m, 0).getDate()
  return Array.from({ length: count }, (_, i) => String(i + 1).padStart(2, '0'))
}

export function splitDate(value: string): { y: string; m: string; d: string } {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value.trim())
  if (m) return { y: m[1], m: m[2], d: m[3] }
  const m2 = /^(\d{4})-(\d{2})$/.exec(value.trim())
  if (m2) return { y: m2[1], m: m2[2], d: '01' }
  return { y: '', m: '', d: '' }
}

export function joinDate(y: string, m: string, d: string): string {
  if (!y || !m || !d) return ''
  return `${y}-${m}-${d}`
}

export function splitRegion(value: string): { province: string; city: string } {
  const parts = value.split(/[·\s]+/).filter(Boolean)
  if (parts.length >= 2) {
    const province = PROVINCES.find((p) => p === parts[0] || p.startsWith(parts[0])) ?? parts[0]
    const city = parts[1]
    return { province, city }
  }
  if (parts.length === 1) {
    const province = PROVINCES.find((p) => p.includes(parts[0]) || parts[0].includes(p.replace(/省|市|自治区|特别行政区/g, '')))
    return { province: province ?? '', city: '' }
  }
  return { province: '', city: '' }
}

export function joinRegion(province: string, city: string): string {
  if (!province) return ''
  if (!city) return province
  return `${province} · ${city}`
}
