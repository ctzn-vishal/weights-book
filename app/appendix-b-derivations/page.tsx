import { chapterPage } from '@/lib/chapter-page';
import Article from './article.mdx';

const { metadata, Page } = chapterPage('appendix-b-derivations', Article);
export { metadata };
export default Page;
