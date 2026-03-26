const fs = require("fs");
const path = require("path");
const { ethers } = require("hardhat");

async function main() {
  const IdentityRegistry = await ethers.getContractFactory("IdentityRegistry");
  const contract = await IdentityRegistry.deploy();
  await contract.waitForDeployment();
  const address = await contract.getAddress();
  const rpcUrl = "http://127.0.0.1:8545";

  const envPath = path.resolve(__dirname, "..", "..", ".env");
  let envContents = "";
  if (fs.existsSync(envPath)) {
    envContents = fs.readFileSync(envPath, "utf8");
  }

  if (envContents.match(/^CONTRACT_ADDRESS=/m)) {
    envContents = envContents.replace(/^CONTRACT_ADDRESS=.*$/m, `CONTRACT_ADDRESS=${address}`);
  } else {
    envContents = `${envContents.trimEnd()}\nCONTRACT_ADDRESS=${address}\n`;
  }

  if (envContents.match(/^GANACHE_URL=/m)) {
    envContents = envContents.replace(/^GANACHE_URL=.*$/m, `GANACHE_URL=${rpcUrl}`);
  } else {
    envContents = `${envContents.trimEnd()}\nGANACHE_URL=${rpcUrl}\n`;
  }

  fs.writeFileSync(envPath, envContents);

  console.log(`CONTRACT_ADDRESS=${address}`);
  console.log(`GANACHE_URL=${rpcUrl}`);
  console.log(`Updated ${envPath}`);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
