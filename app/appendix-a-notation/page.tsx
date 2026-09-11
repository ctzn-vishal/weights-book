import { chapterPage } from '@/lib/chapter-page';
import Article from './article.mdx';

const { metadata, Page } = chapterPage('appendix-a-notation', Article);
export { metadata };
export default Page;
