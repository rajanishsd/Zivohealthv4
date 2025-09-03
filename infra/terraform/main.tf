module "networking" {
  source      = "./modules/networking"
  project     = var.project_name
  environment = var.environment
  vpc_cidr    = var.vpc_cidr
}

module "storage" {
  source      = "./modules/storage"
  project     = var.project_name
  environment = var.environment
  bucket_name = "zivohealth-data"
}

module "iam" {
  source              = "./modules/iam"
  project             = var.project_name
  environment         = var.environment
  storage_bucket_arn  = module.storage.bucket_arn
}

module "ecr" {
  source      = "./modules/ecr"
  project     = var.project_name
  environment = var.environment
}

module "db" {
  source              = "./modules/db"
  project             = var.project_name
  environment         = var.environment
  vpc_id              = module.networking.vpc_id
  private_subnet_ids  = module.networking.private_subnet_ids
  db_username         = var.db_username
  db_password_ssm_key = var.db_password_ssm_name
  db_password         = "zivo_890"
  sg_ids_allowing_db  = [module.networking.ec2_sg_id]
}

module "ssm" {
  source                = "./modules/ssm"
  project               = var.project_name
  environment           = var.environment
  image_tag             = var.image_tag
  db_endpoint           = module.db.endpoint
  db_username           = var.db_username
  db_password_ssm_key   = var.db_password_ssm_name
  s3_bucket_name        = module.storage.bucket_name
  db_password_plain     = "zivo_890"
}

module "compute" {
  source                = "./modules/compute"
  project               = var.project_name
  environment           = var.environment
  vpc_id                = module.networking.vpc_id
  public_subnet_id      = module.networking.public_subnet_ids[0]
  instance_profile_name = module.iam.instance_profile_name
  security_group_ids    = [module.networking.ec2_sg_id]
  ecr_repo_url          = module.ecr.repository_url
  ssm_image_tag_param   = module.ssm.image_tag_param_name
  aws_region            = var.aws_region
  enable_ssh_tunnel     = var.enable_ssh_tunnel
  ssh_allowed_cidrs     = var.ssh_allowed_cidrs
  key_name              = var.ssh_key_name
  valid_api_keys_override = var.valid_api_keys_override
  app_secret_key_override = var.app_secret_key_override
}

module "route53" {
  source      = "./modules/route53"
  project     = var.project_name
  environment = var.environment
  zone_name   = "zivohealth.ai"
  target_ip   = module.compute.public_ip
}
