import type { DesignCatalog } from '@/types/design';
export const designFixture: DesignCatalog = {
  styles: ['商务简约','学术简约','科技风','创意活泼','教育培训','金融专业','杂志编辑','极简黑白','瑞士网格','暖调人文','自然清新','建筑作品集','复古印刷','柔和彩色','大胆宣言','深海蓝金'].map(name => ({name,category:'演示主题',description:'有层次的表达',family:'editorial',primary:'#29483E',secondary:'#75877E',text:'#202B26',background:'#FAF9F6'})),
  layout_modes:[{id:'auto',name:'自动编排',description:'按内容选择'},{id:'editorial',name:'编辑叙事',description:'侧栏与分段'},{id:'structured',name:'规整网格',description:'双栏与模块'},{id:'spotlight',name:'重点聚焦',description:'突出结论'}],
  densities:[{id:'airy',name:'舒展',description:'简短解释'},{id:'balanced',name:'适中',description:'兼顾要点'},{id:'compact',name:'充实',description:'保留细节'}],
};
