import { chapterPage } from '@/lib/chapter-page';
import Article from './article.mdx';

const { metadata, Page } = chapterPage('appendix-c-reproducibility', Article);
export { metadata };
export default Page;
